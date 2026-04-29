from fastapi import Header
from fastapi.responses import JSONResponse


def require_api_version(x_api_version: str = Header(None)):
    if not x_api_version:
        return JSONResponse(
            status_code=400,
            content={
                "status": "error",
                "message": "API version header required"
            }
        )

    if x_api_version != "1":
        return JSONResponse(
            status_code=400,
            content={
                "status": "error",
                "message": "Invalid API version"
            }
        )
    
    