from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from packages.domain.reports import summarize_expenses


@dataclass
class Exp:
    amount_minor: int
    category: str
    paid_at: date


def test_empty():
    s = summarize_expenses([])
    assert s.total_minor == 0
    assert s.count == 0
    assert s.by_category == []
    assert s.by_day == []


def test_aggregation():
    items = [
        Exp(10000, "furniture", date(2026, 5, 1)),
        Exp(20000, "furniture", date(2026, 5, 1)),
        Exp(5000, "decor", date(2026, 5, 2)),
    ]
    s = summarize_expenses(items)
    assert s.total_minor == 35000
    assert s.count == 3
    cats = {r.category: (r.total_minor, r.count) for r in s.by_category}
    assert cats == {"furniture": (30000, 2), "decor": (5000, 1)}
    # by_category sorted by total desc
    assert s.by_category[0].category == "furniture"
    # by_day sorted by date asc
    assert [r.day for r in s.by_day] == [date(2026, 5, 1), date(2026, 5, 2)]
