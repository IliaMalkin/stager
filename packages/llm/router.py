"""LLM router: MiMo primary → Gemini fallback.

Public API: `LLMRouter.chat()`, `LLMRouter.vision()`.

Triggers fallback to Gemini:
- HTTP 401/403 from MiMo (revoke signal — also bumps soft circuit breaker)
- HTTP 429 (rate limit)
- HTTP 5xx
- httpx.TimeoutException
- Pydantic validation fail on structured response
- Any other exception from provider call

Soft circuit breaker: after N consecutive 401/403 events MiMo is blocked
in Redis for TTL seconds and all calls go straight to Gemini.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Literal, TypeVar

import structlog
from pydantic import BaseModel, ValidationError

from packages.llm.circuit_breaker import MimoCircuitBreaker
from packages.llm.providers.gemini import GeminiProvider, GeminiError
from packages.llm.providers.mimo import MimoProvider, MimoError

log = structlog.get_logger(__name__)

T = TypeVar("T", bound=BaseModel)

Complexity = Literal["fast", "smart"]


@dataclass
class LLMCallMeta:
    provider: str            # "mimo" | "gemini"
    model: str
    tokens_in: int
    tokens_out: int
    latency_ms: int
    fallback_reason: str | None
    attempts: int


class LLMRouter:
    def __init__(
        self,
        mimo: MimoProvider,
        gemini: GeminiProvider,
        breaker: MimoCircuitBreaker,
    ) -> None:
        self.mimo = mimo
        self.gemini = gemini
        self.breaker = breaker

    # ──────────────────────────────────────────────────────────────
    # Public
    # ──────────────────────────────────────────────────────────────

    async def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        response_format: type[T] | None = None,
        complexity: Complexity = "fast",
        request_id: str,
    ) -> tuple[T | str, LLMCallMeta]:
        async def _mimo() -> tuple[Any, dict[str, Any]]:
            return await self.mimo.chat(
                messages,
                model=self.mimo.model_for(complexity),
                response_format=response_format,
            )

        async def _gemini() -> tuple[Any, dict[str, Any]]:
            return await self.gemini.chat(
                messages,
                model=self.gemini.model_for(complexity),
                response_format=response_format,
            )

        return await self._with_fallback(
            primary=_mimo,
            fallback=_gemini,
            complexity_label=complexity,
            request_id=request_id,
        )

    async def vision(
        self,
        image_bytes: bytes,
        prompt: str,
        *,
        response_format: type[T],
        request_id: str,
    ) -> tuple[T, LLMCallMeta]:
        async def _mimo() -> tuple[Any, dict[str, Any]]:
            return await self.mimo.vision(
                image_bytes,
                prompt,
                model=self.mimo.model_for("vision"),
                response_format=response_format,
            )

        async def _gemini() -> tuple[Any, dict[str, Any]]:
            return await self.gemini.vision(
                image_bytes,
                prompt,
                model=self.gemini.model_for("vision"),
                response_format=response_format,
            )

        result, meta = await self._with_fallback(
            primary=_mimo,
            fallback=_gemini,
            complexity_label="vision",
            request_id=request_id,
        )
        # vision is always typed
        assert isinstance(result, response_format)
        return result, meta

    # ──────────────────────────────────────────────────────────────
    # Core fallback logic
    # ──────────────────────────────────────────────────────────────

    async def _with_fallback(
        self,
        *,
        primary,
        fallback,
        complexity_label: str,
        request_id: str,
    ) -> tuple[Any, LLMCallMeta]:
        attempts = 0
        fallback_reason: str | None = None
        t0 = time.monotonic()

        # Skip MiMo entirely if circuit breaker is open
        mimo_blocked = await self.breaker.is_open()

        if not mimo_blocked:
            attempts += 1
            try:
                result, usage = await primary()
                meta = LLMCallMeta(
                    provider="mimo",
                    model=usage.get("model", "?"),
                    tokens_in=usage.get("tokens_in", 0),
                    tokens_out=usage.get("tokens_out", 0),
                    latency_ms=int((time.monotonic() - t0) * 1000),
                    fallback_reason=None,
                    attempts=attempts,
                )
                log.info(
                    "llm.call",
                    request_id=request_id,
                    provider="mimo",
                    model=meta.model,
                    tokens_in=meta.tokens_in,
                    tokens_out=meta.tokens_out,
                    latency_ms=meta.latency_ms,
                    complexity=complexity_label,
                    result="success",
                )
                await self.breaker.record_success()
                return result, meta
            except MimoError as exc:
                fallback_reason = exc.reason
                log.warning(
                    "llm.mimo_failed",
                    request_id=request_id,
                    reason=exc.reason,
                    http_status=exc.http_status,
                    complexity=complexity_label,
                )
                if exc.is_auth_failure:
                    await self.breaker.record_auth_failure()
            except ValidationError as exc:
                fallback_reason = "validation_error"
                log.warning(
                    "llm.mimo_validation_failed",
                    request_id=request_id,
                    errors=exc.errors()[:3],
                )
            except Exception as exc:  # noqa: BLE001
                fallback_reason = f"unexpected:{type(exc).__name__}"
                log.exception(
                    "llm.mimo_unexpected", request_id=request_id, error=str(exc)
                )
        else:
            fallback_reason = "circuit_breaker_open"
            log.info("llm.mimo_skipped_breaker", request_id=request_id)

        # Fallback to Gemini
        attempts += 1
        try:
            result, usage = await fallback()
        except GeminiError as exc:
            log.error(
                "llm.both_failed",
                request_id=request_id,
                mimo_reason=fallback_reason,
                gemini_reason=exc.reason,
                http_status=exc.http_status,
            )
            raise

        meta = LLMCallMeta(
            provider="gemini",
            model=usage.get("model", "?"),
            tokens_in=usage.get("tokens_in", 0),
            tokens_out=usage.get("tokens_out", 0),
            latency_ms=int((time.monotonic() - t0) * 1000),
            fallback_reason=fallback_reason,
            attempts=attempts,
        )
        log.info(
            "llm.call",
            request_id=request_id,
            provider="gemini",
            model=meta.model,
            tokens_in=meta.tokens_in,
            tokens_out=meta.tokens_out,
            latency_ms=meta.latency_ms,
            complexity=complexity_label,
            fallback_reason=fallback_reason,
            result="fallback",
        )
        return result, meta
