from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPBearer
from jose import jwt, JWTError
from sqlalchemy.orm import Session

from api.database import get_db
from api.models import User
from api.auth import SECRET, ALGO

security = HTTPBearer()

def get_current_user(
    credentials = Security(security),
    db: Session = Depends(get_db)
):
    token = credentials.credentials

    try:
        payload = jwt.decode(token, SECRET, algorithms=[ALGO])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = db.query(User).filter(User.id == payload["sub"]).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="User inactive")

    return user
