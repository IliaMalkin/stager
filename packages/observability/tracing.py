"""Request-ID propagation через structlog contextvars.

Идея:
- На входе в HTTP-запрос / Telegram-update / Celery-task — генерим request_id (UUID4)
- Кладём в structlog.contextvars — все последующие log-events получат это поле
- LLM router уже принимает request_id отдельным параметром — пробрасываем тот же
"""

from __future__ import annotations

import uuid

import structlog


_KEY = "request_id"


def new_request_id() -> str:
    return uuid.uuid4().hex[:16]


def bind_request_id(request_id: str | None = None) -> str:
    rid = request_id or new_request_id()
    structlog.contextvars.bind_contextvars(request_id=rid)
    return rid


def clear_request_id() -> None:
    structlog.contextvars.unbind_contextvars(_KEY)
