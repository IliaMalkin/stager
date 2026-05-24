from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime


class UserOut(BaseModel):
    id: int
    email: str | None
    full_name: str | None
    role: str
    locale: str
    project_quota: int | None  # None = unlimited

    model_config = {"from_attributes": True}
