"""OCR pipeline: receipt photo → LLM vision → review card в Telegram.

Архитектурные решения:
- Module-level lazy cache для Bot/LLM router — переиспользуем через worker process
- Узкое ретраение: только сетевые/I-O ошибки, программные баги пробрасываем как есть
- Бот сам отправляет review card обратно в чат — chat_id приходит из enqueue-args
- Receipt.raw_ocr_text хранит ИСХОДНЫЙ ответ LLM (audit), а draft для редактирования
  живёт в Redis (apps.bot.drafts)
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

import httpx
import structlog
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from apps.worker.celery_app import celery_app
from packages.db.base import get_sessionmaker
from packages.db.models import Project, Receipt
from packages.domain.categories import label_for
from packages.domain.currency import format_amount
from packages.llm import OCRResult, RECEIPT_OCR_PROMPT, build_router
from packages.llm.providers.gemini import GeminiError
from packages.llm.providers.mimo import MimoError
from packages.storage import build_storage

log = structlog.get_logger(__name__)


# ─── module-level cached singletons ──────────────────────────────────────────
# Каждый Celery-worker процесс держит один Bot и один LLM router. Между tasks
# переиспользуются. asyncio event loop создаётся новый на каждый asyncio.run().

_bot: Bot | None = None
_router: Any = None
_storage: Any = None


def _get_bot() -> Bot:
    global _bot
    if _bot is None:
        _bot = Bot(
            token=os.environ["TELEGRAM_BOT_TOKEN"],
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
    return _bot


def _get_router() -> Any:
    global _router
    if _router is None:
        _router = build_router()
    return _router


def _get_storage() -> Any:
    global _storage
    if _storage is None:
        _storage = build_storage()
    return _storage


# ─── retryable exceptions ────────────────────────────────────────────────────
# Расширяем по мере обнаружения реальных flake-ов на проде. Программные ошибки
# (KeyError, AttributeError) сюда НЕ попадают и убивают task сразу — это правильно.

_RETRYABLE = (
    httpx.HTTPError,
    httpx.TimeoutException,
    ConnectionError,
    OSError,
    MimoError,
    GeminiError,
)


# ─── task ────────────────────────────────────────────────────────────────────

@celery_app.task(name="ocr.process_receipt", bind=True, max_retries=3, default_retry_delay=10)
def process_receipt(
    self,
    receipt_id: int,
    tg_user_id: int,
    chat_id: int,
    project_id: int,
    locale: str = "ru",
) -> dict:
    try:
        return asyncio.run(_run(receipt_id, chat_id, project_id, locale))
    except _RETRYABLE as exc:
        log.warning("ocr.task_retry", receipt_id=receipt_id, error=str(exc), attempt=self.request.retries)
        raise self.retry(exc=exc) from exc


async def _run(receipt_id: int, chat_id: int, project_id: int, locale: str) -> dict:
    # 1. Receipt status check (идемпотентность)
    async with get_sessionmaker()() as session:
        receipt = await session.get(Receipt, receipt_id)
        if not receipt:
            log.warning("ocr.receipt_missing", receipt_id=receipt_id)
            return {"status": "missing"}
        if receipt.ocr_status in ("ok", "needs_review") and receipt.raw_ocr_text:
            log.info("ocr.already_processed", receipt_id=receipt_id)
            return {"status": "already_processed"}
        minio_key = receipt.minio_key
        receipt.ocr_attempts += 1
        await session.commit()

    # 2. Скачиваем картинку + дёргаем LLM
    storage = _get_storage()
    image_bytes = await storage.get_object(minio_key)

    router = _get_router()
    try:
        result, meta = await router.vision(
            image_bytes=image_bytes,
            prompt=RECEIPT_OCR_PROMPT,
            response_format=OCRResult,
            request_id=f"receipt:{receipt_id}",
        )
    except (MimoError, GeminiError) as exc:
        # Оба провайдера упали — записываем failed и шлём извинение
        log.exception("ocr.both_providers_failed", receipt_id=receipt_id)
        async with get_sessionmaker()() as session:
            r = await session.get(Receipt, receipt_id)
            if r:
                r.ocr_status = "failed"
                await session.commit()
        await _send_failed(chat_id, locale)
        return {"status": "failed", "error": str(exc)}

    # 3. Записываем audit + draft
    status = "ok" if result.is_reliable() else "needs_review"
    async with get_sessionmaker()() as session:
        r = await session.get(Receipt, receipt_id)
        if not r:
            return {"status": "missing"}
        r.ocr_status = status
        r.ocr_provider = f"{meta.provider}:{meta.model}"
        # raw_ocr_text — ИММУТАБЕЛЬНЫЙ audit, никогда не перезаписывается callback'ами
        r.raw_ocr_text = json.dumps(
            _result_to_draft_dict(result), ensure_ascii=False, default=str
        )
        await session.commit()

    # Кладём draft в Redis (отдельно от raw_ocr_text)
    from apps.bot.drafts import Draft, ReceiptDraftStore
    drafts = ReceiptDraftStore.from_env()
    try:
        await drafts.set(receipt_id, Draft(**_result_to_draft_dict(result)))
    finally:
        await drafts.redis.aclose()

    # 4. Отправляем review card
    await _send_card(chat_id, receipt_id, project_id, result, locale)
    return {
        "status": status,
        "provider": meta.provider,
        "fallback_reason": meta.fallback_reason,
        "latency_ms": meta.latency_ms,
    }


def _result_to_draft_dict(r: OCRResult) -> dict:
    return {
        "amount": r.amount,
        "currency": r.currency,
        "vendor": r.vendor,
        "date": r.purchased_at.isoformat() if r.purchased_at else None,
        "category": r.category_guess,
        "confidence": r.confidence,
        "items": [it.model_dump() for it in r.items],
    }


async def _send_card(
    chat_id: int,
    receipt_id: int,
    project_id: int,
    result: OCRResult,
    locale: str,
) -> None:
    from apps.bot.i18n import t
    from apps.bot.keyboards import review_card_keyboard

    async with get_sessionmaker()() as session:
        project = await session.get(Project, project_id)
        currency = project.currency if project else "RUB"

    can_save = result.is_reliable()
    amount_str = (
        format_amount(int(round(result.amount * 100)), currency)
        if result.amount is not None
        else "—"
    )
    text = t(
        "photo.card",
        locale,
        vendor=result.vendor or "—",
        amount=amount_str,
        date=result.purchased_at.isoformat() if result.purchased_at else "—",
        category=label_for(result.category_guess, locale),
        warn="" if can_save else t("photo.card_warn_low_confidence", locale),
    )
    bot = _get_bot()
    await bot.send_message(
        chat_id, text,
        reply_markup=review_card_keyboard(receipt_id, can_save=can_save, locale=locale),
    )


async def _send_failed(chat_id: int, locale: str) -> None:
    from apps.bot.i18n import t
    bot = _get_bot()
    await bot.send_message(chat_id, t("photo.ocr_failed", locale))
