"""OCR pipeline: Telegram file_id -> MinIO -> LLM vision -> review card."""

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

_router: Any = None
_storage: Any = None


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


_RETRYABLE = (
    httpx.HTTPError,
    httpx.TimeoutException,
    ConnectionError,
    OSError,
    MimoError,
    GeminiError,
)


@celery_app.task(name="ocr.process_receipt", bind=True, max_retries=3, default_retry_delay=10)
def process_receipt(
    self,
    file_id: str,
    tg_user_id: int,
    chat_id: int,
    project_id: int,
    locale: str = "ru",
) -> dict:
    try:
        return asyncio.run(_run_task(file_id, chat_id, project_id, locale))
    except _RETRYABLE as exc:
        log.warning("ocr.task_retry", file_id=file_id, error=str(exc), attempt=self.request.retries)
        raise self.retry(exc=exc) from exc


async def _run_task(file_id: str, chat_id: int, project_id: int, locale: str) -> dict:
    bot = Bot(
        token=os.environ["TELEGRAM_BOT_TOKEN"],
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    try:
        return await _run(file_id, chat_id, project_id, locale, bot)
    finally:
        await bot.session.close()


async def _run(file_id: str, chat_id: int, project_id: int, locale: str, bot: Bot) -> dict:
    file = await bot.get_file(file_id)
    if not file.file_path:
        raise OSError(f"telegram file has no path: {file_id}")
    buf = await bot.download_file(file.file_path)
    if buf is None:
        raise OSError(f"telegram file download returned empty: {file_id}")
    image_bytes = buf.read()

    storage = _get_storage()
    minio_key = await storage.put_receipt(project_id, image_bytes, filename=f"{file_id}.jpg")

    async with get_sessionmaker()() as session:
        receipt = Receipt(
            minio_key=minio_key,
            original_filename=f"{file_id}.jpg",
            ocr_status="pending",
            ocr_attempts=1,
        )
        session.add(receipt)
        await session.commit()
        receipt_id = receipt.id

    router = _get_router()
    try:
        result, meta = await router.vision(
            image_bytes=image_bytes,
            prompt=RECEIPT_OCR_PROMPT,
            response_format=OCRResult,
            request_id=f"receipt:{receipt_id}",
        )
    except (MimoError, GeminiError) as exc:
        log.exception("ocr.both_providers_failed", receipt_id=receipt_id)
        async with get_sessionmaker()() as session:
            r = await session.get(Receipt, receipt_id)
            if r:
                r.ocr_status = "failed"
                await session.commit()
        await _send_failed(bot, chat_id, locale)
        return {"status": "failed", "error": str(exc)}

    status = "ok" if result.is_reliable() else "needs_review"
    async with get_sessionmaker()() as session:
        r = await session.get(Receipt, receipt_id)
        if not r:
            return {"status": "missing"}
        r.ocr_status = status
        r.ocr_provider = f"{meta.provider}:{meta.model}"
        r.raw_ocr_text = json.dumps(
            _result_to_draft_dict(result), ensure_ascii=False, default=str
        )
        await session.commit()

    from apps.bot.drafts import Draft, ReceiptDraftStore
    drafts = ReceiptDraftStore.from_env()
    try:
        await drafts.set(receipt_id, Draft(**_result_to_draft_dict(result)))
    finally:
        await drafts.redis.aclose()

    await _send_card(bot, chat_id, receipt_id, project_id, result, locale)
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
    bot: Bot,
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
    await bot.send_message(
        chat_id, text,
        reply_markup=review_card_keyboard(receipt_id, can_save=can_save, locale=locale),
    )


async def _send_failed(bot: Bot, chat_id: int, locale: str) -> None:
    from apps.bot.i18n import t
    await bot.send_message(chat_id, t("photo.ocr_failed", locale))
