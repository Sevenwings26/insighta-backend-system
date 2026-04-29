from sqlalchemy import func, asc, desc
from api.models import Profile


# filtering and sorting 
def build_profile_query(
    db,
    gender=None,
    country_id=None,
    age_group=None,
    min_age=None,
    max_age=None,
    min_gender_probability=None,
    min_country_probability=None,
    sort_by="created_at",
    order="desc"
):
    query = db.query(Profile)

    # Filters
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

    # Sorting
    allowed_sort_columns = {
        "age": Profile.age,
        "created_at": Profile.created_at,
        "gender_probability": Profile.gender_probability
    }

    if sort_by not in allowed_sort_columns:
        raise ValueError("Invalid sort field")

    col = allowed_sort_columns[sort_by]

    if order.lower() == "asc":
        query = query.order_by(asc(col), asc(Profile.id))
    else:
        query = query.order_by(desc(col), desc(Profile.id))

    return query
