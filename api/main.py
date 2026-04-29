import httpx
import os
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from contextlib import asynccontextmanager

from api.routes import account, profiles, search
from api.dependencies.auth import get_current_user

from api.middleware.logging import logging_middleware

# Rate limiting 
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi import _rate_limit_exceeded_handler
from fastapi.responses import JSONResponse

from api.middleware.rate_limit import limiter
from api.database import init_db

# Lifespan (connection reuse)
@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup Logic ---
    print("Initializing database...")
    init_db()
    
    # Initialize a shared HTTPX client for external API calls
    app.state.client = httpx.AsyncClient()
    print("System Online: Startup complete.")
    
    yield
    
    # --- Shutdown Logic ---
    print("Shutting down: Closing connections...")
    await app.state.client.aclose()
    print("System Offline.")

app = FastAPI(lifespan=lifespan)

# Middleware
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SESSION_SECRET"))

app.middleware("http")(logging_middleware)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# rate limiting
app.state.limiter = limiter

# app.add_exception_handler(
#     RateLimitExceeded,
#     _rate_limit_exceeded_handler
# )

app.add_middleware(SlowAPIMiddleware)

# Custom 429 Response 
@app.exception_handler(RateLimitExceeded)
async def custom_rate_limit_handler(request, exc):
    return JSONResponse(
        status_code=429,
        content={
            "status": "error",
            "message": "Rate limit exceeded"
        }
    )


# Routers
app.include_router(
    account.router, 
    prefix="/auth", 
    tags=["Auth"]
)

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

# -----------------------------
# GET /
# -----------------------------
@app.get('/')
def root():
    return {
        "project": "Insighta Labs API",

        "slack_name": "Sevenwings",
        "github_repo": "https://github.com/Sevenwings26/insighta-backend-system.git",
        
        "usage": "https://hng-stage1-data-persistence-api-des-swart.vercel.app",
        "documentation": "https://hng-stage1-data-persistence-api-des-swart.vercel.app/docs",
    }


