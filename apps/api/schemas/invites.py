from __future__ import annotations

from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field


class InviteCreate(BaseModel):
    project_id: int | None = None
    role: Literal["editor", "viewer"] = "editor"
    ttl_hours: int = Field(48, ge=1, le=24 * 30)
    # Лимит на создание проектов redeemer'ом. None = unlimited (default).
    # Используй для приглашения assistant'ов с ограничениями (например 3 проекта).
    max_projects: int | None = Field(None, ge=0, le=1000)


class InviteOut(BaseModel):
    token: str
    url: str
    expires_at: datetime
    project_id: int | None
    role: str
    max_projects: int | None
