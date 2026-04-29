from pydantic import BaseModel
from typing import Optional
from datetime import datetime



class ProfileRequest(BaseModel):
    name: str


class ProfileResponse(BaseModel):
    id: str
    name: str
    gender: str
    gender_probability: float
    # sample_size: int
    sample_size: Optional[int] = None
    age: int
    age_group: str
    country_id: str
    country_probability: float
    created_at: datetime

    class Config:
        from_attributes = True


class RefreshTokenRequest(BaseModel):
    refresh_token: str

# class StreamingResponse(BaseModel):
#     id, name, gender, gender_probability, age, age_group, country_id, country_name, country_probability, created_at

#     id: str