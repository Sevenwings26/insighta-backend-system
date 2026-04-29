# backend/routes/auth.py
import os
import secrets
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from typing import Optional

from api.database import get_db
from api.models import User, RefreshToken
from api.auth import oauth, generate_pkce_pair, create_tokens
from api.dependencies.rbac import require_admin, require_analyst
from api.middleware.rate_limit import limiter

router = APIRouter()
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

@router.get("/github")
@limiter.limit("10/minute")
async def github_login(request: Request):
    """Initiate GitHub OAuth with PKCE and CSRF protection"""
    
    # Generate PKCE pair
    code_verifier, code_challenge = generate_pkce_pair()
    
    # Generate CSRF token
    csrf_token = secrets.token_urlsafe(32)
    
    # Store both in session
    request.session["code_verifier"] = code_verifier
    request.session["csrf_token"] = csrf_token
    request.session["csrf_token_time"] = datetime.now(timezone.utc).timestamp()
    
    # Set CSRF cookie (will be validated on callback)
    response = await oauth.github.authorize_redirect(
        request,
        os.getenv("GITHUB_REDIRECT_URI"),
        code_challenge=code_challenge,
        code_challenge_method="S256",
        state=csrf_token,  # CSRF token in state parameter
    )
    
    # Set CSRF cookie
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=True,  # Not accessible via JS
        secure=os.getenv("ENVIRONMENT") == "production",
        samesite="lax",
        max_age=300,  # 5 minutes
    )
    
    return response


@router.get("/github/callback")
async def github_callback(
    request: Request, 
    code: str, 
    state: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Handle GitHub OAuth callback with CSRF validation"""
    
    # 1. Validate CSRF token from state parameter
    stored_csrf = request.session.get("csrf_token")
    cookie_csrf = request.cookies.get("csrf_token")
    
    if not stored_csrf or not cookie_csrf:
        raise HTTPException(status_code=400, detail="Missing CSRF token")
    
    if stored_csrf != cookie_csrf or stored_csrf != state:
        raise HTTPException(status_code=403, detail="CSRF validation failed")
    
    # Check CSRF token age (max 5 minutes)
    csrf_time = request.session.get("csrf_token_time", 0)
    if datetime.now(timezone.utc).timestamp() - csrf_time > 300:
        raise HTTPException(status_code=403, detail="CSRF token expired")
    
    # 2. Clear CSRF tokens from session
    request.session.pop("csrf_token", None)
    request.session.pop("csrf_token_time", None)
    
    # 3. Get PKCE verifier
    code_verifier = request.session.get("code_verifier")
    if not code_verifier:
        raise HTTPException(status_code=400, detail="Missing PKCE verifier")
    
    # 4. Exchange code for access token
    try:
        token = await oauth.github.authorize_access_token(
            request, code_verifier=code_verifier
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"OAuth failed: {str(e)}")
    
    # 5. Fetch user info from GitHub
    resp = await oauth.github.get("user", token=token)
    user_data = resp.json()
    
    github_id = str(user_data["id"])
    
    # 6. Create or retrieve user
    user = db.query(User).filter(User.github_id == github_id).first()
    
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
    
    # 7. Create new tokens
    access_token, refresh_token = create_tokens(user, db)
    
    # 8. Set HTTP-only cookies (meets requirements)
    response = RedirectResponse(url=f"{FRONTEND_URL}/dashboard")
    
    # Access token (short-lived)
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,      # ✅ Not accessible via JavaScript
        secure=os.getenv("ENVIRONMENT") == "production",  # ✅ HTTPS only in production
        samesite="lax",     # ✅ CSRF protection
        max_age=1800,       # 30 minutes (adjust as needed)
        path="/",
    )
    
    # Refresh token (long-lived)
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,      # ✅ Not accessible via JavaScript
        secure=os.getenv("ENVIRONMENT") == "production",
        samesite="lax",
        max_age=604800,     # 7 days
        path="/",
    )
    
    # Clear the PKCE verifier from session
    request.session.pop("code_verifier", None)
    
    return response


# @router.get("/me")
# async def get_current_user(
#     request: Request,
#     db: Session = Depends(get_db)
# ):
#     """Get current user from HTTP-only cookie"""
    
#     access_token = request.cookies.get("access_token")
    
#     if not access_token:
#         raise HTTPException(status_code=401, detail="Not authenticated")
    
#     try:
#         from api.auth import decode_token
#         payload = decode_token(access_token)
#         user_id = payload.get("sub")
        
#         user = db.query(User).filter(User.id == user_id).first()
#         if not user:
#             raise HTTPException(status_code=401, detail="User not found")
        
#         return {
#             "id": user.id,
#             "username": user.username,
#             "email": user.email,
#             "role": user.role,
#             "avatar_url": user.avatar_url,
#             "authenticated": True
#         }
#     except Exception as e:
#         raise HTTPException(status_code=401, detail="Invalid token")


@router.post("/refresh")
async def refresh_token(
    request: Request,
    db: Session = Depends(get_db)
):
    """Refresh access token using HTTP-only cookie"""
    
    refresh_token = request.cookies.get("refresh_token")
    
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Missing refresh token")
    
    # Validate refresh token
    db_token = db.query(RefreshToken).filter(
        RefreshToken.token == refresh_token,
        RefreshToken.is_revoked == False
    ).first()
    
    if not db_token or db_token.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    
    # Revoke old token
    db_token.is_revoked = True
    
    # Get user
    user = db.query(User).filter(User.id == db_token.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Create new tokens
    new_access_token, new_refresh_token = create_tokens(user, db)
    
    # Set new cookies
    response = RedirectResponse(url=request.headers.get("referer", f"{FRONTEND_URL}/dashboard"))
    
    response.set_cookie(
        key="access_token",
        value=new_access_token,
        httponly=True,
        secure=os.getenv("ENVIRONMENT") == "production",
        samesite="lax",
        max_age=1800,
        path="/",
    )
    
    response.set_cookie(
        key="refresh_token",
        value=new_refresh_token,
        httponly=True,
        secure=os.getenv("ENVIRONMENT") == "production",
        samesite="lax",
        max_age=604800,
        path="/",
    )
    
    return response


@router.post("/logout")
async def logout(
    request: Request,
    db: Session = Depends(get_db)
):
    """Logout by revoking refresh token and clearing cookies"""
    
    refresh_token = request.cookies.get("refresh_token")
    
    if refresh_token:
        db_token = db.query(RefreshToken).filter(
            RefreshToken.token == refresh_token
        ).first()
        
        if db_token:
            db_token.is_revoked = True
            db.commit()
    
    # Clear cookies
    response = RedirectResponse(url=f"{FRONTEND_URL}/login")
    
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    response.delete_cookie("csrf_token", path="/")
    
    return response



# import os

# from fastapi import APIRouter, Request, Depends, HTTPException
# from fastapi.responses import RedirectResponse
# from sqlalchemy.orm import Session
# from fastapi import HTTPException
# from jose import JWTError, jwt
# from datetime import datetime, timezone

# from api.database import get_db
# from api.models import User, RefreshToken
# from api.schema import RefreshTokenRequest
# from api.auth import oauth, generate_pkce_pair, create_tokens

# from api.dependencies.rbac import require_admin, require_analyst

# from api.auth import SECRET, ALGO
# from api.middleware.rate_limit import limiter

# router = APIRouter()

# FRONTEND_URL = os.getenv("FRONTEND_URL")


# # # FastAPI backend
# # @router.get("/me")
# # def get_me(user: User = Depends(require_analyst)): # Use your existing dependency
# #     return {
# #         "id": user.id,
# #         "username": user.username,
# #         "email": user.email,
# #         "role": user.role # Important for Admin checks later
# #     }

# @router.get("/github")
# @limiter.limit("10/minute")
# async def github_login(request: Request):
#     code_verifier, code_challenge = generate_pkce_pair()

#     # Store verifier in session
#     request.session["code_verifier"] = code_verifier

#     return await oauth.github.authorize_redirect(
#         request,
#         os.getenv("GITHUB_REDIRECT_URI"),
#         code_challenge=code_challenge,
#         code_challenge_method="S256",
#     )




# @router.get("/github/callback")
# async def github_callback(request: Request, db: Session = Depends(get_db)):
#     code_verifier = request.session.get("code_verifier")

#     if not code_verifier:
#         raise HTTPException(status_code=400, detail="Missing PKCE verifier")

#     token = await oauth.github.authorize_access_token(
#         request, code_verifier=code_verifier
#     )

#     # fetch user info from github
#     resp = await oauth.github.get("user", token=token)
#     user_data = resp.json()

#     github_id = str(user_data["id"])

#     # retrieve user
#     user = db.query(User).filter(User.github_id == github_id).first()

#     # create user 
#     if not user:
#         user = User(
#             github_id=github_id,
#             username=user_data["login"],
#             email=user_data.get("email"),
#             avatar_url=user_data.get("avatar_url"),
#         )
#         db.add(user)

#     user.last_login_at = datetime.now(timezone.utc)
#     db.commit()
#     db.refresh(user)

#     access_token, refresh_token = create_tokens(user, db)

#     # 1. Prepare the redirect to your Next.js Dashboard
#     frontend_dashboard_url = f"{FRONTEND_URL}/dashboard"
#     # frontend_dashboard_url = "http://localhost:3000/dashboard"
#     response = RedirectResponse(url=frontend_dashboard_url)

#     # 2. Set HTTP-only Cookies (Stage 3 Security Requirement)
#     # This allows your Middleware and AuthContext to "see" the user
#     response.set_cookie(
#         key="access_token",
#         value=access_token,
#         httponly=True,   # Critical: Prevent JS theft
#         max_age=180,     # 3 minutes (Stage 3 rule)
#         samesite="lax",
#         secure=False     # Set to True in production (HTTPS)
#     )
    
#     response.set_cookie(
#         key="refresh_token",
#         value=refresh_token,
#         httponly=True,
#         max_age=604800,  # 7 days
#         samesite="lax",
#         secure=False
#     )

#     return response

# @router.post("/refresh")
# def refresh_token(
#     payload: RefreshTokenRequest, 
#     db: Session = Depends(get_db)
# ):
#     token = payload.refresh_token

#     if not token:
#         raise HTTPException(status_code=400, detail="Missing refresh token")

#     try:
#         decoded = jwt.decode(token, SECRET, algorithms=[ALGO])
#     except JWTError:
#         raise HTTPException(status_code=401, detail="Invalid token")

#     # 1. Fetch token from DB
#     db_token = db.query(RefreshToken).filter(
#         RefreshToken.token == token
#     ).first()

#     if not db_token:
#         raise HTTPException(status_code=401, detail="Token not found")

#     # 2. Check revoked
#     if db_token.is_revoked:
#         raise HTTPException(status_code=401, detail="Token already revoked")

#     # 3. Check expiry (DB-level)
#     if db_token.expires_at < datetime.now(timezone.utc):
#         raise HTTPException(status_code=401, detail="Token expired")

#     # 4. Revoke old token (CRITICAL)
#     db_token.is_revoked = True

#     user = db.query(User).filter(User.id == db_token.user_id).first()

#     if not user:
#         raise HTTPException(status_code=404, detail="User not found")

#     # 5. Issue new tokens
#     access_token, new_refresh_token = create_tokens(user, db)

#     return {
#         "status": "success",
#         "access_token": access_token,
#         "refresh_token": new_refresh_token
#     }


# @router.post("/logout")
# def logout(payload: RefreshTokenRequest, db: Session = Depends(get_db)):
#     token = payload.refresh_token

#     if not token:
#         raise HTTPException(status_code=400, detail="Missing refresh token")

#     db_token = db.query(RefreshToken).filter(
#         RefreshToken.token == token
#     ).first()

#     if not db_token:
#         raise HTTPException(status_code=401, detail="Token not found")

#     db_token.is_revoked = True
#     db.commit()

#     return {"status": "success"}

