"""Google Gemini provider — fallback for MiMo.

Uses google-genai SDK. Free tier ~1M tokens/day.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, TypeVar

from google import genai
from google.genai import errors as genai_errors
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class GeminiError(Exception):
    def __init__(self, reason: str, *, http_status: int | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.http_status = http_status


@dataclass
class GeminiConfig:
    api_key: str
    model_vision: str = "gemini-2.5-flash"
    model_fast: str = "gemini-2.5-flash"
    model_smart: str = "gemini-2.5-pro"


class GeminiProvider:
    def __init__(self, config: GeminiConfig, client: genai.Client | None = None) -> None:
        self.config = config
        self._client = client or genai.Client(api_key=config.api_key)

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
        prompt = _flatten_messages(messages)
        cfg: dict[str, Any] = {}
        if response_format is not None:
            cfg["response_mime_type"] = "application/json"
            cfg["response_schema"] = response_format
        try:
            resp = await self._client.aio.models.generate_content(
                model=model, contents=prompt, config=cfg or None,
            )
        except genai_errors.APIError as exc:
            raise GeminiError(f"api_error:{exc!s}", http_status=getattr(exc, "code", None)) from exc

        usage = self._usage(resp, model)
        text = resp.text or ""
        if response_format is None:
            return text, usage
        # google-genai populates resp.parsed when response_schema is given
        parsed = getattr(resp, "parsed", None)
        if parsed is None:
            parsed = response_format.model_validate_json(text)
        return parsed, usage

    async def vision(
        self,
        image_bytes: bytes,
        prompt: str,
        *,
        model: str,
        response_format: type[T],
    ) -> tuple[T, dict[str, Any]]:
        try:
            resp = await self._client.aio.models.generate_content(
                model=model,
                contents=[
                    prompt,
                    genai.types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
                ],
                config={
                    "response_mime_type": "application/json",
                    "response_schema": response_format,
                },
            )
        except genai_errors.APIError as exc:
            raise GeminiError(f"api_error:{exc!s}", http_status=getattr(exc, "code", None)) from exc

        parsed = getattr(resp, "parsed", None) or response_format.model_validate_json(resp.text or "")
        return parsed, self._usage(resp, model)

    @staticmethod
    def _usage(resp: Any, model: str) -> dict[str, Any]:
        u = getattr(resp, "usage_metadata", None)
        return {
            "model": model,
            "tokens_in": getattr(u, "prompt_token_count", 0) or 0,
            "tokens_out": getattr(u, "candidates_token_count", 0) or 0,
        }


def _flatten_messages(messages: list[dict[str, Any]]) -> str:
    """Gemini doesn't speak OpenAI message format natively for simple text chat —
    we flatten to a single string for the MVP. System prompt prepended as plain text."""
    parts: list[str] = []
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        if isinstance(content, list):
            content = " ".join(c.get("text", "") for c in content if c.get("type") == "text")
        parts.append(f"{role.upper()}: {content}")
    return "\n\n".join(parts)
