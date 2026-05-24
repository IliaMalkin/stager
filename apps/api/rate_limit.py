"""slowapi rate-limiter — Redis-backed, чтобы лимиты переживали перезапуски и работали
across multiple uvicorn workers."""

from __future__ import annotations

import os

from slowapi import Limiter
from slowapi.util import get_remote_address


def _redis_uri() -> str:
    # slowapi/limits использует свой формат URI
    url = os.getenv("REDIS_URL", "redis://redis:6379/0")
    return url.replace("redis://", "redis://", 1)


limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=_redis_uri(),
    default_limits=[],  # глобального лимита нет — навешиваем точечно
    headers_enabled=True,
)
