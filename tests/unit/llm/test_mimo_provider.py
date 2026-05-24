"""Тесты MimoProvider — что HTTP-ошибки правильно мапятся в MimoError."""

from __future__ import annotations

import httpx
import pytest
import respx

from packages.llm.providers.mimo import MimoConfig, MimoError, MimoProvider


@pytest.fixture
def provider():
    config = MimoConfig(api_key="test-key", base_url="https://mimo.test/v1")
    client = httpx.AsyncClient(
        base_url=config.base_url,
        headers={"Authorization": f"Bearer {config.api_key}"},
    )
    return MimoProvider(config, client=client)


@respx.mock
async def test_chat_ok(provider):
    respx.post("https://mimo.test/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "hi"}}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 2},
            },
        )
    )
    content, usage = await provider.chat([{"role": "user", "content": "x"}], model="mimo-v2.5")
    assert content == "hi"
    assert usage["tokens_in"] == 5


@respx.mock
async def test_chat_429(provider):
    respx.post("https://mimo.test/v1/chat/completions").mock(
        return_value=httpx.Response(429, text="rate")
    )
    with pytest.raises(MimoError) as e:
        await provider.chat([{"role": "user", "content": "x"}], model="mimo-v2.5")
    assert e.value.reason == "rate_limited"
    assert e.value.http_status == 429


@respx.mock
async def test_chat_401_flags_auth_failure(provider):
    respx.post("https://mimo.test/v1/chat/completions").mock(
        return_value=httpx.Response(401, text="bye")
    )
    with pytest.raises(MimoError) as e:
        await provider.chat([{"role": "user", "content": "x"}], model="mimo-v2.5")
    assert e.value.is_auth_failure is True


@respx.mock
async def test_chat_5xx(provider):
    respx.post("https://mimo.test/v1/chat/completions").mock(
        return_value=httpx.Response(503, text="oops")
    )
    with pytest.raises(MimoError) as e:
        await provider.chat([{"role": "user", "content": "x"}], model="mimo-v2.5")
    assert "503" in e.value.reason


@respx.mock
async def test_chat_timeout(provider):
    respx.post("https://mimo.test/v1/chat/completions").mock(
        side_effect=httpx.TimeoutException("slow")
    )
    with pytest.raises(MimoError) as e:
        await provider.chat([{"role": "user", "content": "x"}], model="mimo-v2.5")
    assert e.value.reason == "timeout"
