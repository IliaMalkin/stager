"""Soft circuit breaker for MiMo. Backed by Redis.

After N consecutive 401/403 events from MiMo we set a TTL key. While the key
is alive, the router skips MiMo entirely and goes straight to Gemini.

Why soft: MiMo grant can be revoked at any time per ToS. We want graceful
degradation, not a hard outage.
"""

from __future__ import annotations

from redis.asyncio import Redis

_KEY_FAILS = "stager:llm:mimo:consecutive_auth_fails"
_KEY_OPEN = "stager:llm:mimo:disabled_until"


class MimoCircuitBreaker:
    def __init__(
        self,
        redis: Redis,
        *,
        fail_threshold: int = 3,
        ttl_seconds: int = 3600,
    ) -> None:
        self.redis = redis
        self.fail_threshold = fail_threshold
        self.ttl_seconds = ttl_seconds

    async def is_open(self) -> bool:
        return bool(await self.redis.exists(_KEY_OPEN))

    async def record_auth_failure(self) -> None:
        fails = await self.redis.incr(_KEY_FAILS)
        await self.redis.expire(_KEY_FAILS, 600)  # window 10min
        if fails >= self.fail_threshold:
            await self.redis.set(_KEY_OPEN, "1", ex=self.ttl_seconds)
            await self.redis.delete(_KEY_FAILS)

    async def record_success(self) -> None:
        await self.redis.delete(_KEY_FAILS)

    async def force_close(self) -> None:
        """Admin override: re-enable MiMo immediately."""
        await self.redis.delete(_KEY_OPEN, _KEY_FAILS)
