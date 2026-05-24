from __future__ import annotations

from datetime import date, datetime
from pydantic import BaseModel, Field

from packages.domain.categories import Category


class ExpenseCreate(BaseModel):
    amount_minor: int = Field(..., ge=0)
    category: Category
    description: str | None = None
    paid_at: date


class ExpenseUpdate(BaseModel):
    amount_minor: int | None = Field(None, ge=0)
    category: Category | None = None
    description: str | None = None
    paid_at: date | None = None


class ExpenseOut(BaseModel):
    id: int
    project_id: int
    amount_minor: int
    currency: str
    category: str
    description: str | None
    paid_at: date
    source: str
    created_at: datetime

    model_config = {"from_attributes": True}
