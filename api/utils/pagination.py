from math import ceil
from urllib.parse import urlencode


def build_pagination_response(
    *,
    request,
    query,
    page: int,
    limit: int,
    serializer
):
    total = query.count()
    total_pages = ceil(total / limit) if total > 0 else 1

    # Clamp page (important for edge cases)
    if page > total_pages:
        page = total_pages

    skip = (page - 1) * limit
    results = query.offset(skip).limit(limit).all()

    base_url = str(request.url).split("?")[0]

    def build_link(p):
        if p < 1 or p > total_pages:
            return None
        params = dict(request.query_params)
        params.update({"page": p, "limit": limit})
        return f"{base_url}?{urlencode(params)}"

    return {
        "status": "success",
        "page": page,
        "limit": limit,
        "total": total,
        "total_pages": total_pages,
        "links": {
            "self": build_link(page),
            "next": build_link(page + 1),
            "prev": build_link(page - 1),
        },
        "data": [serializer(item) for item in results]
    }
