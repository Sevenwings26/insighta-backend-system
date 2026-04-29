from authlib.integrations.starlette_client import OAuth
from fastapi import Request
import os
import secrets
import hashlib
import base64
from dotenv import load_dotenv
from jose import jwt
from datetime import datetime, timedelta, timezone

from api.database import get_db
from api.models import RefreshToken

from sqlalchemy.orm import Session

load_dotenv()
SECRET = os.getenv("JWT_SECRET")
ALGO = "HS256"

# Oauth setup
oauth = OAuth()

oauth.register(
    name="github",
    client_id=os.getenv("GITHUB_CLIENT_ID"),
    client_secret=os.getenv("GITHUB_CLIENT_SECRET"),
    access_token_url="https://github.com/login/oauth/access_token",
    authorize_url="https://github.com/login/oauth/authorize",
    api_base_url="https://api.github.com/",
    client_kwargs={"scope": "user:email"},
)


# pkce implementation
def generate_pkce_pair():
    code_verifier = secrets.token_urlsafe(64)
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).rstrip(b"=").decode("utf-8")

    return code_verifier, code_challenge


# 
def create_tokens(user, db: Session):
    now = datetime.now(timezone.utc)

    access_payload = {
        "sub": user.id,
        "role": user.role.value,
        "exp": now + timedelta(minutes=3)
    }

    refresh_payload = {
        "sub": user.id,
        "type": "refresh",
        "exp": now + timedelta(minutes=5)
    }

    access_token = jwt.encode(access_payload, SECRET, algorithm=ALGO)
    refresh_token = jwt.encode(refresh_payload, SECRET, algorithm=ALGO)

    # ✅ Persist refresh token
    db_token = RefreshToken(
        user_id=user.id,
        token=refresh_token,
        expires_at=now + timedelta(minutes=5)
    )

    db.add(db_token)
    db.commit()

    return access_token, refresh_token



# access_token, refresh_token = create_tokens(user, db)

