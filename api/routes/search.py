# api/routes/search.py
import re
import httpx
import asyncio
from fastapi import APIRouter, Query, Depends, Request
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, asc
from fastapi.responses import JSONResponse
from api.dependencies.rbac import require_admin, require_analyst
from api.dependencies.versioning import require_api_version
from api.utils.pagination import build_pagination_response

import os
from api.database import get_db
from api.models import Profile, User
from api.schema import ProfileRequest, ProfileResponse

router = APIRouter(
    dependencies=[Depends(require_api_version)]
)

# -----------------------------
# GET /api/profiles/search
# -----------------------------
# Mapping for common countries in the seed data
COUNTRY_MAP = {
    "nigeria": "NG",
    "kenya": "KE",
    "angola": "AO",
    "tanzania": "TZ",
    "ghana": "GH",
    "uganda": "UG"
}



@router.get("/search")
def natural_language_search(
    request: Request,
    q: str = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    user: User = Depends(require_analyst)
):
    if not q or q.strip() == "":
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": "Invalid query parameters"}
        )

    query = db.query(Profile)
    text = q.lower().strip()
    interpreted = False

    # Gender
    if "female" in text:
        query = query.filter(func.lower(Profile.gender) == "female")
        interpreted = True
    elif "male" in text:
        query = query.filter(func.lower(Profile.gender) == "male")
        interpreted = True

    # Age groups
    if "young" in text:
        query = query.filter(Profile.age >= 16, Profile.age <= 24)
        interpreted = True

    if "child" in text:
        query = query.filter(Profile.age_group == "child")
        interpreted = True

    if "teenager" in text:
        query = query.filter(Profile.age_group == "teenager")
        interpreted = True

    if "adult" in text:
        query = query.filter(Profile.age_group == "adult")
        interpreted = True

    if "senior" in text:
        query = query.filter(Profile.age_group == "senior")
        interpreted = True

    # Numeric parsing
    age_match = re.search(r'(above|over|below|under|at)\s+(\d+)', text)
    if age_match:
        condition, value = age_match.groups()
        value = int(value)

        if condition in ["above", "over"]:
            query = query.filter(Profile.age > value)
        elif condition in ["below", "under"]:
            query = query.filter(Profile.age < value)
        elif condition == "at":
            query = query.filter(Profile.age == value)

        interpreted = True

    # Country
    for country_name, code in COUNTRY_MAP.items():
        if country_name in text:
            query = query.filter(Profile.country_id == code)
            interpreted = True
            break

    if not interpreted:
        return JSONResponse(
            status_code=422,
            content={"status": "error", "message": "Unable to interpret query"}
        )

    # total = query.count()
    # skip = (page - 1) * limit
    # results = query.offset(skip).limit(limit).all()

    return build_pagination_response(
        request=request,
        query=query,
        page=page,
        limit=limit,
        serializer=lambda p: ProfileResponse.model_validate(p)
    )



