from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from dotenv import load_dotenv
import os

load_dotenv()

raw_url = os.getenv("DATABASE_URL")

if raw_url.startswith("postgres://"):
    DATABASE_URL = raw_url.replace(
        "postgres://",
        "postgresql://",
        1
    )
else:
    DATABASE_URL = raw_url

engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# from api.models import *

# Base.metadata.create_all(bind=engine)

# # database.py

def init_db():
    from api.models import Profile, User, RefreshToken

    Base.metadata.create_all(bind=engine)

