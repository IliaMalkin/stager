"""Receipt draft store — Redis-backed, 24h TTL.

Зачем отдельно от Receipt.raw_ocr_text:
- raw_ocr_text — иммутабельная аудит-запись изначального ответа LLM
- draft — то что юзер видит и редактирует между нажатиями кнопок до Save

Ключ: stager:receipt_draft:{receipt_id}
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from redis.asyncio import Redis

_KEY_TMPL = "stager:receipt_draft:{rid}"
_TTL_SECONDS = 24 * 3600


@dataclass
class Draft:
    amount: float | None = None
    currency: str = "RUB"
    vendor: str | None = None
    date: str | None = None  # ISO YYYY-MM-DD
    category: str = "other"
    confidence: float = 0.0
    items: list[dict[str, Any]] | None = None

    def to_json(self) -> str:
        return json.dumps(
            {
                "amount": self.amount,
                "currency": self.currency,
                "vendor": self.vendor,
                "date": self.date,
                "category": self.category,
                "confidence": self.confidence,
                "items": self.items or [],
            },
            ensure_ascii=False,
        )

    @classmethod
    def from_json(cls, raw: str | bytes) -> "Draft":
        data = json.loads(raw)
        return cls(
            amount=data.get("amount"),
            currency=data.get("currency", "RUB"),
            vendor=data.get("vendor"),
            date=data.get("date"),
            category=data.get("category", "other"),
            confidence=float(data.get("confidence") or 0.0),
            items=data.get("items") or [],
        )

    def is_ready_to_save(self) -> bool:
        return self.amount is not None


class ReceiptDraftStore:
    """Async Redis wrapper for receipt drafts."""

    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    @classmethod
    def from_env(cls) -> "ReceiptDraftStore":
        return cls(Redis.from_url(os.environ["REDIS_URL"]))

    async def set(self, receipt_id: int, draft: Draft) -> None:
        await self.redis.set(_KEY_TMPL.format(rid=receipt_id), draft.to_json(), ex=_TTL_SECONDS)

    async def get(self, receipt_id: int) -> Draft | None:
        raw = await self.redis.get(_KEY_TMPL.format(rid=receipt_id))
        if raw is None:
            return None
        return Draft.from_json(raw)

    async def update(self, receipt_id: int, **patch: Any) -> Draft | None:
        draft = await self.get(receipt_id)
        if draft is None:
            return None
        for k, v in patch.items():
            if hasattr(draft, k):
                setattr(draft, k, v)
        await self.set(receipt_id, draft)
        return draft

    async def clear(self, receipt_id: int) -> None:
        await self.redis.delete(_KEY_TMPL.format(rid=receipt_id))
