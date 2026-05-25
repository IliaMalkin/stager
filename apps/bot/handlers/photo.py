"""Photo handler — main flow.

1. Принимаем фото, ack сразу
2. Скачиваем bytes → MinIO put → создаём Receipt(pending)
3. Enqueue Celery `ocr.process_receipt`
4. Worker дописывает Receipt.raw_ocr_text (audit) + кладёт draft в Redis +
   отправляет review-card обратно

Inline-кнопки карточки обрабатываются здесь, draft живёт в Redis 24ч.
"""

from __future__ import annotations

from datetime import date as dt_date, datetime
from typing import Any

from aiogram import Bot, F, Router, types
from aiogram.fsm.context import FSMContext
from sqlalchemy import select

from apps.bot.drafts import ReceiptDraftStore
from apps.bot.fsm.states import PhotoReviewStates
from apps.bot.i18n import t
from apps.bot.keyboards import category_picker_keyboard, review_card_keyboard
from apps.worker.celery_app import celery_app
from packages.db.base import get_sessionmaker
from packages.db.models import ActiveContext, Expense, Project, Receipt, User
from packages.domain.categories import label_for, parse_category
from packages.domain.currency import format_amount, parse_amount_to_minor
from packages.storage import build_storage

router = Router(name="photo")


# ─── входное фото ─────────────────────────────────────────────────────────────

@router.message(F.photo)
async def on_photo(message: types.Message, bot: Bot, state: FSMContext, locale: str = "ru") -> None:
    tg = message.from_user
    if not tg or not message.photo:
        return

    async with get_sessionmaker()() as session:
        user = await session.scalar(select(User).where(User.telegram_id == tg.id))
        if not user:
            return
        ctx = await session.get(ActiveContext, user.id)
        if not ctx or not ctx.current_project_id:
            await message.answer(t("photo.no_active_project", locale))
            return
        project_id = ctx.current_project_id

    await message.answer(t("photo.ack", locale))

    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    if not file.file_path:
        return
    buf = await bot.download_file(file.file_path)
    if buf is None:
        return
    data = buf.read()

    storage = build_storage()
    minio_key = await storage.put_receipt(project_id, data, filename=f"{photo.file_unique_id}.jpg")

    async with get_sessionmaker()() as session:
        receipt = Receipt(
            minio_key=minio_key,
            original_filename=f"{photo.file_unique_id}.jpg",
            ocr_status="pending",
        )
        session.add(receipt)
        await session.commit()
        receipt_id = receipt.id

    celery_app.send_task(
        "ocr.process_receipt",
        args=[receipt_id, tg.id, message.chat.id, project_id, locale],
    )


# ─── inline-кнопки карточки ──────────────────────────────────────────────────

@router.callback_query(F.data.startswith("rcpt:save:"))
async def cb_save(query: types.CallbackQuery, locale: str = "ru") -> None:
    receipt_id = _rid(query)
    if receipt_id is None or not query.from_user:
        return

    drafts = ReceiptDraftStore.from_env()
    try:
        draft = await drafts.get(receipt_id)
    finally:
        await drafts.redis.aclose()

    if draft is None or not draft.is_ready_to_save():
        await query.answer("Сумма не определена. Поправь вручную.", show_alert=True)
        return

    async with get_sessionmaker()() as session:
        receipt = await session.get(Receipt, receipt_id)
        if not receipt or receipt.ocr_status not in ("ok", "needs_review"):
            await query.answer("⚠️", show_alert=True)
            return
        if receipt.expense_id is not None:
            await query.answer("Уже сохранено.")
            return

        user = await session.scalar(select(User).where(User.telegram_id == query.from_user.id))
        if not user:
            return
        ctx = await session.get(ActiveContext, user.id)
        if not ctx or not ctx.current_project_id:
            await query.answer(t("projects.no_active", locale), show_alert=True)
            return
        project = await session.get(Project, ctx.current_project_id)
        if not project:
            return

        expense = Expense(
            project_id=project.id,
            amount_minor=int(round(float(draft.amount) * 100)),  # type: ignore[arg-type]
            currency=project.currency,
            category=draft.category or "other",
            description=draft.vendor,
            paid_at=_parse_date(draft.date),
            created_by_user_id=user.id,
            source="bot_photo",
            receipt_id=receipt.id,
            raw_ocr_json={
                "amount": draft.amount,
                "currency": draft.currency,
                "vendor": draft.vendor,
                "date": draft.date,
                "category": draft.category,
                "confidence": draft.confidence,
                "items": draft.items,
            },
        )
        session.add(expense)
        await session.flush()
        receipt.expense_id = expense.id
        await session.commit()
        project_name = project.name

    drafts = ReceiptDraftStore.from_env()
    try:
        await drafts.clear(receipt_id)
    finally:
        await drafts.redis.aclose()

    if query.message:
        try:
            await query.message.edit_reply_markup(reply_markup=None)
        except Exception:  # noqa: BLE001
            pass
        await query.message.answer(t("photo.saved", locale, project=project_name))
    await query.answer("✅")


@router.callback_query(F.data.startswith("rcpt:cancel:"))
async def cb_cancel(query: types.CallbackQuery, state: FSMContext, locale: str = "ru") -> None:
    receipt_id = _rid(query)
    if receipt_id is None:
        return
    await state.clear()
    drafts = ReceiptDraftStore.from_env()
    try:
        await drafts.clear(receipt_id)
    finally:
        await drafts.redis.aclose()
    if query.message:
        try:
            await query.message.edit_reply_markup(reply_markup=None)
        except Exception:  # noqa: BLE001
            pass
        await query.message.answer(t("photo.cancelled", locale))
    await query.answer()


@router.callback_query(F.data.startswith("rcpt:edit_amount:"))
async def cb_edit_amount(query: types.CallbackQuery, state: FSMContext) -> None:
    receipt_id = _rid(query)
    if receipt_id is None:
        return
    await state.set_state(PhotoReviewStates.edit_amount)
    await state.update_data(receipt_id=receipt_id)
    await query.answer()
    if query.message:
        await query.message.answer("Введи сумму (например: 4850.50)")


@router.message(PhotoReviewStates.edit_amount)
async def edit_amount_input(message: types.Message, state: FSMContext, locale: str = "ru") -> None:
    try:
        minor = parse_amount_to_minor(message.text or "")
    except ValueError:
        await message.answer("Не понял. Введи число, например 4850.50")
        return
    data = await state.get_data()
    receipt_id = data.get("receipt_id")
    if not receipt_id:
        await state.clear()
        return
    drafts = ReceiptDraftStore.from_env()
    try:
        await drafts.update(receipt_id, amount=minor / 100.0)
    finally:
        await drafts.redis.aclose()
    await state.clear()
    await _resend_card(message, receipt_id, locale)


@router.callback_query(F.data.startswith("rcpt:edit_category:"))
async def cb_edit_category(query: types.CallbackQuery, locale: str = "ru") -> None:
    receipt_id = _rid(query)
    if receipt_id is None:
        return
    await query.answer()
    if query.message:
        await query.message.answer(
            "Выбери категорию:",
            reply_markup=category_picker_keyboard(receipt_id, locale),
        )


@router.callback_query(F.data.startswith("rcpt:set_category:"))
async def cb_set_category(query: types.CallbackQuery, locale: str = "ru") -> None:
    if not query.data:
        return
    parts = query.data.split(":")
    if len(parts) != 4:
        return
    receipt_id = int(parts[2])
    key = parts[3]
    if parse_category(key) is None:
        return
    drafts = ReceiptDraftStore.from_env()
    try:
        await drafts.update(receipt_id, category=key)
    finally:
        await drafts.redis.aclose()
    await query.answer(f"✓ {label_for(key, locale)}")  # type: ignore[arg-type]
    if query.message:
        await _resend_card(query.message, receipt_id, locale)


@router.callback_query(F.data.startswith("rcpt:edit_vendor:"))
async def cb_edit_vendor(query: types.CallbackQuery, state: FSMContext) -> None:
    receipt_id = _rid(query)
    if receipt_id is None:
        return
    await state.set_state(PhotoReviewStates.edit_vendor)
    await state.update_data(receipt_id=receipt_id)
    await query.answer()
    if query.message:
        await query.message.answer("Введи название вендора:")


@router.message(PhotoReviewStates.edit_vendor)
async def edit_vendor_input(message: types.Message, state: FSMContext, locale: str = "ru") -> None:
    vendor = (message.text or "").strip()[:256]
    if not vendor:
        return
    data = await state.get_data()
    receipt_id = data.get("receipt_id")
    if not receipt_id:
        await state.clear()
        return
    drafts = ReceiptDraftStore.from_env()
    try:
        await drafts.update(receipt_id, vendor=vendor)
    finally:
        await drafts.redis.aclose()
    await state.clear()
    await _resend_card(message, receipt_id, locale)


# ─── helpers ─────────────────────────────────────────────────────────────────

def _rid(query: types.CallbackQuery) -> int | None:
    if not query.data:
        return None
    try:
        return int(query.data.split(":")[2])
    except (IndexError, ValueError):
        return None


def _parse_date(value: Any) -> dt_date:
    if not value:
        return dt_date.today()
    if isinstance(value, dt_date):
        return value
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except ValueError:
        return dt_date.today()


async def _resend_card(message: types.Message, receipt_id: int, locale: str) -> None:
    drafts = ReceiptDraftStore.from_env()
    try:
        draft = await drafts.get(receipt_id)
    finally:
        await drafts.redis.aclose()
    if draft is None:
        await message.answer("⚠️ Чек устарел (>24ч), запиши ещё раз: /add")
        return

    can_save = draft.is_ready_to_save()
    amount_str = (
        format_amount(int(round(float(draft.amount) * 100)), draft.currency)
        if draft.amount is not None
        else "—"
    )
    text = t(
        "photo.card",
        locale,
        vendor=draft.vendor or "—",
        amount=amount_str,
        date=draft.date or "—",
        category=label_for(draft.category, locale),  # type: ignore[arg-type]
        warn="" if can_save else t("photo.card_warn_low_confidence", locale),
    )
    await message.answer(
        text,
        reply_markup=review_card_keyboard(receipt_id, can_save=can_save, locale=locale),
    )
