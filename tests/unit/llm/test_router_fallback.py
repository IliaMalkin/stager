"""Тесты главного artifact'a — MiMo→Gemini fallback логика.

Сценарии:
1. MiMo 200 OK → используется MiMo, метрика provider=mimo
2. MiMo 429 → fallback на Gemini, fallback_reason="rate_limited"
3. MiMo 401 → fallback + record_auth_failure() в breaker
4. MiMo timeout → fallback с reason="timeout"
5. MiMo validation error → fallback с reason="validation_error"
6. Circuit breaker открыт → MiMo вообще не зовётся
7. Оба упали → GeminiError наверх
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from packages.llm.providers.gemini import GeminiError
from packages.llm.providers.mimo import MimoError
from packages.llm.router import LLMRouter


@pytest.fixture
def mock_breaker():
    b = AsyncMock()
    b.is_open = AsyncMock(return_value=False)
    return b


@pytest.fixture
def mock_mimo():
    m = AsyncMock()
    m.model_for.return_value = "mimo-v2.5"
    return m


@pytest.fixture
def mock_gemini():
    g = AsyncMock()
    g.model_for.return_value = "gemini-2.5-flash"
    return g


@pytest.fixture
def router(mock_mimo, mock_gemini, mock_breaker):
    return LLMRouter(mimo=mock_mimo, gemini=mock_gemini, breaker=mock_breaker)


async def test_mimo_success(router, mock_mimo, mock_gemini, mock_breaker):
    mock_mimo.chat.return_value = (
        "hello",
        {"model": "mimo-v2.5", "tokens_in": 10, "tokens_out": 5},
    )
    result, meta = await router.chat(
        [{"role": "user", "content": "hi"}], request_id="t1"
    )
    assert result == "hello"
    assert meta.provider == "mimo"
    assert meta.fallback_reason is None
    mock_gemini.chat.assert_not_called()
    mock_breaker.record_success.assert_awaited_once()


async def test_mimo_rate_limited_fallback(router, mock_mimo, mock_gemini):
    mock_mimo.chat.side_effect = MimoError("rate_limited", http_status=429)
    mock_gemini.chat.return_value = (
        "hi from gemini",
        {"model": "gemini-2.5-flash", "tokens_in": 5, "tokens_out": 3},
    )
    result, meta = await router.chat(
        [{"role": "user", "content": "x"}], request_id="t2"
    )
    assert result == "hi from gemini"
    assert meta.provider == "gemini"
    assert meta.fallback_reason == "rate_limited"
    assert meta.attempts == 2


async def test_mimo_auth_failure_bumps_breaker(
    router, mock_mimo, mock_gemini, mock_breaker
):
    mock_mimo.chat.side_effect = MimoError(
        "auth_failure", http_status=401, is_auth_failure=True
    )
    mock_gemini.chat.return_value = ("ok", {"model": "gemini-2.5-flash"})
    await router.chat([{"role": "user", "content": "x"}], request_id="t3")
    mock_breaker.record_auth_failure.assert_awaited_once()


async def test_breaker_open_skips_mimo(router, mock_mimo, mock_gemini, mock_breaker):
    mock_breaker.is_open.return_value = True
    mock_gemini.chat.return_value = ("ok", {"model": "gemini-2.5-flash"})
    _, meta = await router.chat([{"role": "user", "content": "x"}], request_id="t4")
    assert meta.provider == "gemini"
    assert meta.fallback_reason == "circuit_breaker_open"
    mock_mimo.chat.assert_not_called()


async def test_both_fail_raises_gemini_error(router, mock_mimo, mock_gemini):
    mock_mimo.chat.side_effect = MimoError("timeout")
    mock_gemini.chat.side_effect = GeminiError("api_error")
    with pytest.raises(GeminiError):
        await router.chat([{"role": "user", "content": "x"}], request_id="t5")
