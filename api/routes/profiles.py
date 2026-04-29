import os
import io
import csv
import httpx
import asyncio
from fastapi import APIRouter, Query, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse          # ✅ correct import
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, asc
from datetime import datetime
from api.database import get_db
from api.models import Profile, User
from api.schema import ProfileRequest, ProfileResponse
from api.dependencies.rbac import require_admin, require_analyst
from api.dependencies.versioning import require_api_version
from api.utils.pagination import build_pagination_response
from api.utils.query_builder import build_profile_query
from api.middleware.rate_limit import limiter


router = APIRouter(
    dependencies=[Depends(require_api_version)]
)


def classify_age_group(age: int) -> str:
    if age <= 12:
        return "child"
    elif age <= 19:
        return "teenager"
    elif age <= 59:
        return "adult"
    return "senior"


# -----------------------------
# POST /api/profiles
# -----------------------------
@router.post("", status_code=201)
async def create_profile(
    payload: ProfileRequest,                            # ✅ fixed typo: paylaod → payload
    db: Session = Depends(get_db),
    user: User = Depends(require_admin)
):
    name = payload.name
    if not name or name.strip() == "":
        raise HTTPException(status_code=400, detail="Missing or empty name")

    normalized_name = name.strip().lower()

    existing = db.query(Profile).filter(
        func.lower(Profile.name) == normalized_name
    ).first()

    if existing:
        return {
            "status": "success",
            "message": "Profile already exists",
            "data": existing
        }

    async with httpx.AsyncClient(timeout=5.0) as client:
        gender_task = client.get(f"https://api.genderize.io?name={normalized_name}")
        age_task = client.get(f"https://api.agify.io?name={normalized_name}")
        country_task = client.get(f"https://api.nationalize.io?name={normalized_name}")

        gender_res, age_res, country_res = await asyncio.gather(
            gender_task, age_task, country_task
        )

    gen_data = gender_res.json()
    age_data = age_res.json()
    nat_data = country_res.json()

    if (
        gen_data.get("gender") is None
        or gen_data.get("count", 0) == 0
        or age_data.get("age") is None
        or not nat_data.get("country")
    ):
        raise HTTPException(status_code=502, detail="Upstream failure")

    age = age_data["age"]
    age_group = classify_age_group(age)

    top_country = max(
        nat_data["country"],
        key=lambda x: x["probability"]
    )

    profile = Profile(
        name=normalized_name,
        gender=gen_data["gender"],
        gender_probability=gen_data["probability"],
        sample_size=gen_data["count"],
        age=age,
        age_group=age_group,
        country_id=top_country["country_id"],
        country_probability=top_country["probability"],
    )

    db.add(profile)
    db.commit()
    db.refresh(profile)

    return {"status": "success", "data": profile}


# -----------------------------
# GET /api/profiles/export       ✅ MUST be before /{id}
# -----------------------------
@router.get("/export")
def export_profiles(
    format: str = Query("csv"),
    gender: str | None = None,
    country_id: str | None = None,
    age_group: str | None = None,
    min_age: int | None = None,
    max_age: int | None = None,
    min_gender_probability: float | None = None,
    min_country_probability: float | None = None,
    sort_by: str = "created_at",
    order: str = "desc",
    db: Session = Depends(get_db),
    user: User = Depends(require_analyst)
):
    if format != "csv":
        raise HTTPException(status_code=400, detail="Only CSV format is supported")

    try:
        query = build_profile_query(
            db=db,
            gender=gender,
            country_id=country_id,
            age_group=age_group,
            min_age=min_age,
            max_age=max_age,
            min_gender_probability=min_gender_probability,
            min_country_probability=min_country_probability,
            sort_by=sort_by,
            order=order
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid sort field")

    results = query.all()

    def generate():
        buffer = io.StringIO()
        writer = csv.writer(buffer)

        writer.writerow([
            "id", "name",
            "gender", "gender_probability",
            "sample_size", "age",
            "age_group", "country_id",
            "country_probability", "created_at"   # ✅ 10 columns, matches rows below
        ])
        yield buffer.getvalue()
        buffer.seek(0)
        buffer.truncate(0)

        for p in results:
            writer.writerow([
                p.id,
                p.name,
                p.gender,
                p.gender_probability,
                p.sample_size,
                p.age,
                p.age_group,
                p.country_id,
                # ✅ removed stray "Unknown" — country_id IS the identifier
                p.country_probability,
                p.created_at.isoformat() if p.created_at else None
            ])
            yield buffer.getvalue()
            buffer.seek(0)
            buffer.truncate(0)

    filename = f"profiles_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.csv"

    return StreamingResponse(                          # ✅ correct response class
        generate(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


# -----------------------------
# GET /api/profiles
# -----------------------------
@router.get("")
@limiter.limit("60/minute")
def list_profiles(
    request: Request,
    gender: str | None = None,
    country_id: str | None = None,
    age_group: str | None = None,
    min_age: int | None = None,
    max_age: int | None = None,
    min_gender_probability: float | None = None,
    min_country_probability: float | None = None,
    sort_by: str = "created_at",
    order: str = "desc",
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    user: User = Depends(require_analyst)
):
    query = db.query(Profile)

    if gender:
        query = query.filter(func.lower(Profile.gender) == gender.lower())
    if country_id:
        query = query.filter(func.lower(Profile.country_id) == country_id.lower())
    if age_group:
        query = query.filter(func.lower(Profile.age_group) == age_group.lower())
    if min_age is not None:
        query = query.filter(Profile.age >= min_age)
    if max_age is not None:
        query = query.filter(Profile.age <= max_age)
    if min_gender_probability is not None:
        query = query.filter(Profile.gender_probability >= min_gender_probability)
    if min_country_probability is not None:
        query = query.filter(Profile.country_probability >= min_country_probability)

    allowed_sort_columns = {
        "age": Profile.age,
        "created_at": Profile.created_at,
        "gender_probability": Profile.gender_probability
    }

    if sort_by not in allowed_sort_columns:
        raise HTTPException(status_code=400, detail="Invalid sort field")

    target_column = allowed_sort_columns[sort_by]

    if order.lower() == "asc":
        query = query.order_by(asc(target_column), asc(Profile.id))
    else:
        query = query.order_by(desc(target_column), desc(Profile.id))

    return build_pagination_response(
        request=request,
        query=query,
        page=page,
        limit=limit,
        serializer=lambda p: ProfileResponse.model_validate(p)
    )


# -----------------------------
# GET /api/profiles/{id}
# -----------------------------
@router.get("/{id}")
def get_profile(
    id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_analyst)
):
    profile = db.query(Profile).filter(Profile.id == id).first()

    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    return {
        "status": "success",
        "data": ProfileResponse.model_validate(profile)
    }


# -----------------------------
# DELETE /api/profiles/{id}      ✅ path is just /{id}, not /api/profiles/{id}
# -----------------------------
@router.delete("/{id}", status_code=204)
def delete_profile(
    id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin)
):
    profile = db.query(Profile).filter(Profile.id == id).first()

    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    db.delete(profile)
    db.commit()
    


# import os
# import io
# import csv
# import httpx
# import asyncio
# from fastapi import APIRouter, Query, Depends, HTTPException, Request
# from sqlalchemy.orm import Session
# from sqlalchemy import func, desc, asc
# from datetime import datetime
# from api.database import get_db
# from api.models import Profile, User
# from api.schema import ProfileRequest, ProfileResponse
# from api.dependencies.rbac import require_admin, require_analyst
# from api.dependencies.versioning import require_api_version
# from api.utils.pagination import build_pagination_response
# from api.utils.query_builder import build_profile_query
# from api.middleware.rate_limit import limiter


# # router 
# router = APIRouter(
#     dependencies=[Depends(require_api_version)]
# )

# # Helper: Age Group Classifier
# def classify_age_group(age: int) -> str:
#     if age <= 12:
#         return "child"
#     elif age <= 19:
#         return "teenager"
#     elif age <= 59:
#         return "adult"
#     return "senior"


# # -----------------------------
# # POST /api/profiles
# # -----------------------------
# @router.post("", status_code=201)
# async def create_profile(
#     paylaod: ProfileRequest,
#     db: Session = Depends(get_db),
#     user: User = Depends(require_admin)
# ):
#     name = paylaod.name
#     # 1. Validation - if not empty
#     if not name or name.strip() == "":
#         raise HTTPException(status_code=400, detail="Missing or empty name")

#     normalized_name = name.strip().lower()

#     # 2. Idempotency check... To avoid duplicate of same data
#     existing = db.query(Profile).filter(
#         func.lower(Profile.name) == normalized_name
#     ).first()

#     if existing:
#         return {
#             "status": "success",
#             "message": "Profile already exists",
#             "data": existing
#         }

#     # 3. Concurrent API calls
#     async with httpx.AsyncClient(timeout=5.0) as client:
#         gender_task = client.get(f"https://api.genderize.io?name={normalized_name}")
#         age_task = client.get(f"https://api.agify.io?name={normalized_name}")
#         country_task = client.get(f"https://api.nationalize.io?name={normalized_name}")

#         gender_res, age_res, country_res = await asyncio.gather(
#             gender_task, age_task, country_task
#         )

#     # collect data 
#     gen_data = gender_res.json()
#     age_data = age_res.json()
#     nat_data = country_res.json()

#     # 4. Edge case validation (STRICT)
#     if (
#         gen_data.get("gender") is None
#         or gen_data.get("count", 0) == 0
#         or age_data.get("age") is None
#         or not nat_data.get("country")
#     ):
#         raise HTTPException(status_code=502, detail="Upstream failure")

#     # 5. Process data
#     age = age_data["age"]
#     age_group = classify_age_group(age)

#     top_country = max(
#         nat_data["country"],
#         key=lambda x: x["probability"]
#     )

#     # 6. Persist - Save to DB..
#     profile = Profile(
#         name=normalized_name,
#         gender=gen_data["gender"],
#         gender_probability=gen_data["probability"],
#         sample_size=gen_data["count"],
#         age=age,
#         age_group=age_group,
#         country_id=top_country["country_id"],
#         country_probability=top_country["probability"],
#     )

#     db.add(profile)
#     db.commit()
#     db.refresh(profile)

#     return {
#         "status": "success",
#         "data": profile
#     }


# # -----------------------------
# # GET /api/profiles
# # -----------------------------
# @router.get("")
# @limiter.limit("60/minute")
# def list_profiles(
#     request: Request,
#     # Filters
#     gender: str | None = None,
#     country_id: str | None = None,
#     age_group: str | None = None,
#     min_age: int | None = None,
#     max_age: int | None = None,
#     min_gender_probability: float | None = None,
#     min_country_probability: float | None = None,
#     # Sorting & Pagination
#     sort_by: str = "created_at",
#     order: str = "desc",
#     page: int = Query(1, ge=1),
#     limit: int = Query(10, ge=1, le=50),  
#     # limit: int = Query(None), # Manual capping 
#     db: Session = Depends(get_db),
#     user: User = Depends(require_analyst)
# ):
#     query = db.query(Profile)

#     # 1. Advanced Filtering Logic
#     if gender:
#         query = query.filter(func.lower(Profile.gender) == gender.lower())
#     if country_id:
#         query = query.filter(func.lower(Profile.country_id) == country_id.lower())
#     if age_group:
#         query = query.filter(func.lower(Profile.age_group) == age_group.lower())
    
#     # Range Filters (The "Intelligence" part)
#     if min_age is not None:
#         query = query.filter(Profile.age >= min_age)
#     if max_age is not None:
#         query = query.filter(Profile.age <= max_age)
#     if min_gender_probability is not None:
#         query = query.filter(Profile.gender_probability >= min_gender_probability)
#     if min_country_probability is not None:
#         query = query.filter(Profile.country_probability >= min_country_probability)

#     # 2. Sorting Logic
#     # Map the user input string to the actual Database Columns
#     allowed_sort_columns = {
#         "age": Profile.age,
#         "created_at": Profile.created_at,
#         "gender_probability": Profile.gender_probability
#     }

#     if sort_by not in allowed_sort_columns:
#         raise HTTPException(status_code=400, detail="Invalid sort field")

#     target_column = allowed_sort_columns[sort_by]

#     if order.lower() == "asc":
#         query = query.order_by(asc(target_column), asc(Profile.id))
#     else:
#         query = query.order_by(desc(target_column), desc(Profile.id))

#     return build_pagination_response(
#         request=request,
#         query=query,
#         page=page,
#         limit=limit,
#         serializer=lambda p: ProfileResponse.model_validate(p)
#     )



# # -----------------------------
# # GET /api/profiles{id}
# # -----------------------------
# @router.get("/{id}")
# def get_profile(
#     id: str, 
#     db: Session = Depends(get_db),
#     user: User = Depends(require_analyst)
# ):
#     profile = db.query(Profile).filter(Profile.id == id).first()

#     if not profile:
#         raise HTTPException(status_code=404, detail="Profile not found")

#     return {
#         "status": "success",
#     #   "data": profile
#         "data": ProfileResponse.model_validate(profile)
#     }


# # -----------------------------
# # DELETE /api/profiles/{id} - admin only
# # -----------------------------
# @router.delete("/api/profiles/{id}", status_code=204)
# def delete_profile(
#     id: str, 
#     db: Session = Depends(get_db),
#     user: User = Depends(require_admin)
# ):
#     profile = db.query(Profile).filter(Profile.id == id).first()

#     if not profile:
#         raise HTTPException(status_code=404, detail="Profile not found")

#     db.delete(profile)
#     db.commit()


# @router.get("/export")
# def export_profiles(
#     format: str = Query("csv"),
#     # Filters
#     gender: str | None = None,
#     country_id: str | None = None,
#     age_group: str | None = None,
#     min_age: int | None = None,
#     max_age: int | None = None,
#     min_gender_probability: float | None = None,
#     min_country_probability: float | None = None,
#     # Sorting
#     sort_by: str = "created_at",
#     order: str = "desc",
#     db: Session = Depends(get_db),
#     user: User = Depends(require_analyst)
# ):
#     if format != "csv":
#         raise HTTPException(
#             status_code=400,
#             detail="Only CSV format is supported"
#         )

#     # Build query (REUSE logic)
#     try:
#         query = build_profile_query(
#             db=db,
#             gender=gender,
#             country_id=country_id,
#             age_group=age_group,
#             min_age=min_age,
#             max_age=max_age,
#             min_gender_probability=min_gender_probability,
#             min_country_probability=min_country_probability,
#             sort_by=sort_by,
#             order=order
#         )
#     except ValueError:
#         raise HTTPException(status_code=400, detail="Invalid sort field")

#     results = query.all()

#     # Create CSV stream
#     def generate():
#         buffer = io.StringIO()
#         writer = csv.writer(buffer)

#         # Header
#         writer.writerow([ 
#             "id", "name",
#             "gender", "gender_probability",
#             "sample_size", "age",
#             "age_group", "country_id",
#             "country_probability", "created_at" 
#             ])

#         yield buffer.getvalue()
#         buffer.seek(0)
#         buffer.truncate(0)

#         # Rows
#         for p in results:
#             writer.writerow([
#                 p.id,
#                 p.name,
#                 p.gender,
#                 p.gender_probability,
#                 p.sample_size,
#                 p.age,
#                 p.age_group,
#                 p.country_id,
#                 "Unknown", # Replace with real country name lookup if available
#                 p.country_probability,
#                 p.created_at.isoformat() if p.created_at else None
#             ])

#             yield buffer.getvalue()
#             buffer.seek(0)
#             buffer.truncate(0)

#     filename = f"profiles_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.csv"

#     return ProfileResponse(
#         generate(),
#         media_type="text/csv",
#         headers={
#             "Content-Disposition": f'attachment; filename="{filename}"'
#         }
#     )
