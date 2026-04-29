from fastapi import Depends, HTTPException
from api.dependencies.auth import get_current_user
from api.models import User, UserRole


def require_roles(*allowed_roles: UserRole):
    def role_checker(user: User = Depends(get_current_user)):
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail="Insufficient permissions"
            )
        return user
    return role_checker


# Convenience wrappers (cleaner usage)
def require_admin(user: User = Depends(require_roles(UserRole.ADMIN))):
    return user


def require_analyst(user: User = Depends(require_roles(UserRole.ADMIN, UserRole.ANALYST))):
    return user
