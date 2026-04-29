import os

from fastapi import APIRouter, Request, Depends, HTTPException
from sqlalchemy.orm import Session
from fastapi import HTTPException
from jose import JWTError, jwt
from datetime import datetime, timezone

from api.database import get_db
from api.models import User, RefreshToken
from api.schema import RefreshTokenRequest
from api.auth import oauth, generate_pkce_pair, create_tokens

from api.auth import SECRET, ALGO
from api.middleware.rate_limit import limiter

router = APIRouter()


@router.get("/github")
@limiter.limit("10/minute")
async def github_login(request: Request):
    code_verifier, code_challenge = generate_pkce_pair()

    # Store verifier in session
    request.session["code_verifier"] = code_verifier

    return await oauth.github.authorize_redirect(
        request,
        os.getenv("GITHUB_REDIRECT_URI"),
        code_challenge=code_challenge,
        code_challenge_method="S256",
    )


@router.get("/github/callback")
async def github_callback(request: Request, db: Session = Depends(get_db)):
    code_verifier = request.session.get("code_verifier")

    if not code_verifier:
        raise HTTPException(status_code=400, detail="Missing PKCE verifier")

    token = await oauth.github.authorize_access_token(
        request, code_verifier=code_verifier
    )

    # fetch user info from github
    resp = await oauth.github.get("user", token=token)
    user_data = resp.json()

    github_id = str(user_data["id"])

    # retrieve user
    user = db.query(User).filter(User.github_id == github_id).first()

    # create user 
    if not user:
        user = User(
            github_id=github_id,
            username=user_data["login"],
            email=user_data.get("email"),
            avatar_url=user_data.get("avatar_url"),
        )
        db.add(user)

    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)

    access_token, refresh_token = create_tokens(user, db)

    return {
        "status": "success",
        "access_token": access_token,
        "refresh_token": refresh_token
    }


@router.post("/refresh")
def refresh_token(
    payload: RefreshTokenRequest, 
    db: Session = Depends(get_db)
):
    token = payload.refresh_token

    if not token:
        raise HTTPException(status_code=400, detail="Missing refresh token")

    try:
        decoded = jwt.decode(token, SECRET, algorithms=[ALGO])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    # 1. Fetch token from DB
    db_token = db.query(RefreshToken).filter(
        RefreshToken.token == token
    ).first()

    if not db_token:
        raise HTTPException(status_code=401, detail="Token not found")

    # 2. Check revoked
    if db_token.is_revoked:
        raise HTTPException(status_code=401, detail="Token already revoked")

    # 3. Check expiry (DB-level)
    if db_token.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Token expired")

    # 4. Revoke old token (CRITICAL)
    db_token.is_revoked = True

    user = db.query(User).filter(User.id == db_token.user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 5. Issue new tokens
    access_token, new_refresh_token = create_tokens(user, db)

    return {
        "status": "success",
        "access_token": access_token,
        "refresh_token": new_refresh_token
    }


@router.post("/logout")
def logout(payload: RefreshTokenRequest, db: Session = Depends(get_db)):
    token = payload.refresh_token

    if not token:
        raise HTTPException(status_code=400, detail="Missing refresh token")

    db_token = db.query(RefreshToken).filter(
        RefreshToken.token == token
    ).first()

    if not db_token:
        raise HTTPException(status_code=401, detail="Token not found")

    db_token.is_revoked = True
    db.commit()

    return {"status": "success"}

