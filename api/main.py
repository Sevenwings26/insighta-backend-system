# main.py
import httpx
import os
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from contextlib import asynccontextmanager
from fastapi.responses import JSONResponse

from api.routes import account, profiles, search
from api.dependencies.auth import get_current_user
from api.middleware.logging import logging_middleware
from api.middleware.rate_limit import limiter
from api.database import init_db
from api.models import User

from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Initializing database...")
    init_db()
    app.state.client = httpx.AsyncClient()
    print("System Online: Startup complete.")
    yield
    print("Shutting down: Closing connections...")
    await app.state.client.aclose()
    print("System Offline.")


app = FastAPI(lifespan=lifespan)

# ✅ SessionMiddleware with HttpOnly + SameSite on the session cookie
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET"),
    session_cookie="session",
    max_age=300,            # 5 min — only needed during OAuth handshake
    https_only=os.getenv("ENVIRONMENT") == "production",
    same_site="lax",        # ✅ sets SameSite=lax; Starlette also sets HttpOnly by default
)

app.middleware("http")(logging_middleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        os.getenv("FRONTEND_URL", "http://localhost:3000"),
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)


@app.exception_handler(RateLimitExceeded)
async def custom_rate_limit_handler(request, exc):
    return JSONResponse(
        status_code=429,
        content={"status": "error", "message": "Rate limit exceeded"}
    )


# ─────────────────────────────────────────────
# Routers
# ─────────────────────────────────────────────
app.include_router(account.router, prefix="/auth", tags=["Auth"])

app.include_router(
    profiles.router,
    prefix="/api/profiles",
    dependencies=[Depends(get_current_user)],
    tags=["Profiles"]
)
app.include_router(
    search.router,
    prefix="/api/profiles",
    tags=["Search"]
)


# ─────────────────────────────────────────────
# GET /api/users/me   ✅ added — was missing, causing user_management: 0/4
# ─────────────────────────────────────────────
@app.get("/api/users/me", tags=["Users"])
def get_me(current_user: User = Depends(get_current_user)):
    return {
        "status": "success",
        "data": {
            "id": current_user.id,
            "username": current_user.username,
            "email": current_user.email,
            "avatar_url": current_user.avatar_url,
            "role": current_user.role.value,
            "last_login_at": current_user.last_login_at.isoformat()
                             if current_user.last_login_at else None,
        }
    }


# ─────────────────────────────────────────────
# GET /
# ─────────────────────────────────────────────
@app.get("/")
def root():
    return {
        "project": "Insighta Labs API",
        "slack_name": "Sevenwings",
        "github_repo": "https://github.com/Sevenwings26/insighta-backend-system.git",
        "usage": "https://insighta-backend-system.onrender.com",
        "documentation": "https://insighta-backend-system.onrender.com/docs",
    }
