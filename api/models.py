# from sqlalchemy.ext.declarative import declarative_base

import enum
from sqlalchemy import Column, String, Float, Integer, DateTime, func, Enum, Boolean, ForeignKey
from uuid_utils import uuid7
from api.database import Base



# model 
class UserRole(enum.Enum):
    ADMIN = "admin"
    ANALYST = "analyst"


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid7()))
    github_id = Column(String, unique=True, nullable=False, index=True)
    username = Column(String, nullable=False)
    email = Column(String, index=True)
    avatar_url = Column(String)
    role = Column(Enum(UserRole), default=UserRole.ANALYST, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from datetime import datetime, timezone, timedelta

class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(String, primary_key=True, default=lambda: str(uuid7()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    token = Column(String, unique=True, nullable=False)

    is_revoked = Column(Boolean, default=False, nullable=False)

    expires_at = Column(DateTime(timezone=True), nullable=False)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )


class Profile(Base):
    __tablename__ = "profiles"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid7()))
    name = Column(String, unique=True, index=True, nullable=False)
    gender = Column(String)
    gender_probability = Column(Float)
    sample_size = Column(Integer)
    age = Column(Integer)
    age_group = Column(String)
    country_id = Column(String)
    country_probability = Column(Float)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()  # handles UTC
    )


# 