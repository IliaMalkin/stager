from __future__ import annotations

from datetime import date
from pydantic import BaseModel


class CategoryRowOut(BaseModel):
    category: str
    total_minor: int
    count: int


class DayRowOut(BaseModel):
    day: date
    total_minor: int
    count: int


class ProjectSummaryOut(BaseModel):
    project_id: int
    total_minor: int
    count: int
    currency: str
    by_category: list[CategoryRowOut]
    by_day: list[DayRowOut]
