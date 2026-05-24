"""Логика проверки квоты на создание проектов. Без I/O — чистая функция."""

from __future__ import annotations


class QuotaExceeded(Exception):
    """Поднимается когда юзер пытается создать проект сверх квоты."""

    def __init__(self, quota: int) -> None:
        super().__init__(f"Project creation quota exceeded ({quota} projects)")
        self.quota = quota


def check_quota(remaining: int | None) -> None:
    """remaining = User.project_quota (None = unlimited).
    Бросает QuotaExceeded если квота исчерпана."""
    if remaining is None:
        return
    if remaining <= 0:
        raise QuotaExceeded(quota=0)


def decrement_quota(remaining: int | None) -> int | None:
    """После успешного создания проекта. None остаётся None (unlimited)."""
    if remaining is None:
        return None
    return max(0, remaining - 1)
