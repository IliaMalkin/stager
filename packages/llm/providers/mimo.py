"""MiMo (Xiaomi) provider — OpenAI-compatible API.

Endpoint: https://token-plan-sgp.xiaomimimo.com/v1
Models: mimo-v2-omni (vision), mimo-v2.5 (fast text), mimo-v2.5-pro (smart text).
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Any, Literal, TypeVar

import httpx
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class MimoError(Exception):
    def __init__(
        self,
        reason: str,
        *,
        http_status: int | None = None,
        is_auth_failure: bool = False,
    ) -> None:
        super().__init__(reason)
        self.reason = reason
        self.http_status = http_status
        self.is_auth_failure = is_auth_failure


@dataclass
class MimoConfig:
    api_key: str
    base_url: str = "https://token-plan-sgp.xiaomimimo.com/v1"
    model_vision: str = "mimo-v2-omni"
    model_fast: str = "mimo-v2.5"
    model_smart: str = "mimo-v2.5-pro"
    timeout_chat: float = 15.0
    timeout_vision: float = 30.0


class MimoProvider:
    def __init__(self, config: MimoConfig, client: httpx.AsyncClient | None = None) -> None:
        self.config = config
        self._client = client or httpx.AsyncClient(
            base_url=config.base_url,
            headers={"Authorization": f"Bearer {config.api_key}"},
        )

    def model_for(self, complexity: Literal["fast", "smart", "vision"]) -> str:
        return {
            "fast": self.config.model_fast,
            "smart": self.config.model_smart,
            "vision": self.config.model_vision,
        }[complexity]

    async def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str,
        response_format: type[T] | None = None,
    ) -> tuple[T | str, dict[str, Any]]:
        payload: dict[str, Any] = {"model": model, "messages": messages}
        if response_format is not None:
            payload["response_format"] = {"type": "json_object"}

        data = await self._post("/chat/completions", payload, timeout=self.config.timeout_chat)
        content = data["choices"][0]["message"]["content"]
        usage = self._usage(data, model)

        if response_format is None:
            return content, usage
        parsed = response_format.model_validate_json(_strip_json(content))
        return parsed, usage

    async def vision(
        self,
        image_bytes: bytes,
        prompt: str,
        *,
        model: str,
        response_format: type[T],
    ) -> tuple[T, dict[str, Any]]:
        b64 = base64.b64encode(image_bytes).decode()
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                    },
                ],
            }
        ]
        payload = {
            "model": model,
            "messages": messages,
            "response_format": {"type": "json_object"},
        }
        data = await self._post("/chat/completions", payload, timeout=self.config.timeout_vision)
        content = data["choices"][0]["message"]["content"]
        parsed = response_format.model_validate_json(_strip_json(content))
        return parsed, self._usage(data, model)

    # ───── internals ─────

    async def _post(
        self, path: str, payload: dict[str, Any], *, timeout: float
    ) -> dict[str, Any]:
        try:
            resp = await self._client.post(path, json=payload, timeout=timeout)
        except httpx.TimeoutException as exc:
            raise MimoError("timeout") from exc
        except httpx.HTTPError as exc:
            raise MimoError(f"network:{type(exc).__name__}") from exc

        if resp.status_code in (401, 403):
            raise MimoError(
                "auth_failure",
                http_status=resp.status_code,
                is_auth_failure=True,
            )
        if resp.status_code == 429:
            raise MimoError("rate_limited", http_status=429)
        if resp.status_code >= 500:
            raise MimoError(f"http_{resp.status_code}", http_status=resp.status_code)
        if resp.status_code >= 400:
            raise MimoError(
                f"http_{resp.status_code}:{resp.text[:200]}",
                http_status=resp.status_code,
            )
        return resp.json()

    @staticmethod
    def _usage(data: dict[str, Any], model: str) -> dict[str, Any]:
        u = data.get("usage", {})
        return {
            "model": model,
            "tokens_in": u.get("prompt_tokens", 0),
            "tokens_out": u.get("completion_tokens", 0),
        }


def _strip_json(text: str) -> str:
    """Strip markdown fences if model added them despite instructions."""
    t = text.strip()
    if t.startswith("```"):
        # ```json\n{...}\n```  or ```\n{...}\n```
        t = t.split("\n", 1)[1] if "\n" in t else t[3:]
        if t.endswith("```"):
            t = t[:-3]
    return t.strip()
