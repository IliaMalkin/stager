"""Чистая агрегация — никакого I/O. Вход: список dict-подобных expense, выход: ProjectSummary."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from typing import Iterable, Protocol


class ExpenseLike(Protocol):
    amount_minor: int
    category: str
    paid_at: date


@dataclass
class CategoryRow:
    category: str
    total_minor: int
    count: int


@dataclass
class DayRow:
    day: date
    total_minor: int
    count: int


@dataclass
class ProjectSummary:
    total_minor: int
    count: int
    by_category: list[CategoryRow] = field(default_factory=list)
    by_day: list[DayRow] = field(default_factory=list)


def summarize_expenses(expenses: Iterable[ExpenseLike]) -> ProjectSummary:
    total = 0
    count = 0
    by_cat_total: dict[str, int] = defaultdict(int)
    by_cat_count: dict[str, int] = defaultdict(int)
    by_day_total: dict[date, int] = defaultdict(int)
    by_day_count: dict[date, int] = defaultdict(int)

    for e in expenses:
        total += e.amount_minor
        count += 1
        by_cat_total[e.category] += e.amount_minor
        by_cat_count[e.category] += 1
        by_day_total[e.paid_at] += e.amount_minor
        by_day_count[e.paid_at] += 1

    by_category = sorted(
        (
            CategoryRow(category=c, total_minor=by_cat_total[c], count=by_cat_count[c])
            for c in by_cat_total
        ),
        key=lambda r: r.total_minor,
        reverse=True,
    )
    by_day = sorted(
        (
            DayRow(day=d, total_minor=by_day_total[d], count=by_day_count[d])
            for d in by_day_total
        ),
        key=lambda r: r.day,
    )

    return ProjectSummary(
        total_minor=total,
        count=count,
        by_category=by_category,
        by_day=by_day,
    )
