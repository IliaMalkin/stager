"""Build a wired LLMRouter from env-based settings."""

from __future__ import annotations

import os

from redis.asyncio import Redis

from packages.llm.circuit_breaker import MimoCircuitBreaker
from packages.llm.providers.gemini import GeminiConfig, GeminiProvider
from packages.llm.providers.mimo import MimoConfig, MimoProvider
from packages.llm.router import LLMRouter


def build_router(redis: Redis | None = None) -> LLMRouter:
    mimo = MimoProvider(
        MimoConfig(
            api_key=os.environ["MIMO_API_KEY"],
            base_url=os.getenv("MIMO_BASE_URL", "https://token-plan-sgp.xiaomimimo.com/v1"),
            model_vision=os.getenv("MIMO_MODEL_VISION", "mimo-v2-omni"),
            model_fast=os.getenv("MIMO_MODEL_FAST", "mimo-v2.5"),
            model_smart=os.getenv("MIMO_MODEL_SMART", "mimo-v2.5-pro"),
        )
    )
    gemini = GeminiProvider(
        GeminiConfig(
            api_key=os.environ["GOOGLE_API_KEY"],
            model_vision=os.getenv("GEMINI_MODEL_VISION", "gemini-2.5-flash"),
            model_fast=os.getenv("GEMINI_MODEL_FAST", "gemini-2.5-flash"),
            model_smart=os.getenv("GEMINI_MODEL_SMART", "gemini-2.5-pro"),
        )
    )
    r = redis or Redis.from_url(os.environ["REDIS_URL"])
    breaker = MimoCircuitBreaker(
        r,
        fail_threshold=int(os.getenv("LLM_MIMO_SOFT_DISABLE_AFTER", "3")),
        ttl_seconds=int(os.getenv("LLM_MIMO_SOFT_DISABLE_TTL", "3600")),
    )
    return LLMRouter(mimo=mimo, gemini=gemini, breaker=breaker)
