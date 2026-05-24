from __future__ import annotations

from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=256)
    currency: str = "RUB"
    budget_minor: int | None = None


class ProjectUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=256)
    status: Literal["active", "completed", "archived"] | None = None
    budget_minor: int | None = None


class ProjectOut(BaseModel):
    id: int
    name: str
    currency: str
    budget_minor: int | None
    status: str
    owner_user_id: int
    created_at: datetime

    model_config = {"from_attributes": True}
