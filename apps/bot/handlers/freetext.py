"""Free-text expense fallback.

This router must be registered last: it intentionally catches stateless text
that was not handled by commands, FSM dialogs, or photo flows.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Any
from uuid import uuid4

from aiogram import F, Router, types
from aiogram.filters import StateFilter
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select

from apps.bot.drafts import FreeTextDraft, FreeTextDraftStore
from apps.bot.i18n import t
from packages.db.models import ActiveContext, Expense, Project, User
from packages.domain.categories import label_for
from packages.domain.currency import format_amount, parse_amount_to_minor

router = Router(name="freetext")

_NUMBER_RE = r"(?:\d+(?:[ \u00a0]\d{3})*(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?)"
_PLUS_RE = re.compile(rf"{_NUMBER_RE}(?:\s*\+\s*{_NUMBER_RE})+")
_THOUSAND_RE = re.compile(rf"{_NUMBER_RE}\s*(?:тыс\.?|тысяч[аи]?|т\.)", re.IGNORECASE)
_CURRENCY_RE = re.compile(rf"{_NUMBER_RE}\s*(?:₽|руб\.?|р\.?|rub|rur)", re.IGNORECASE)
_SIMPLE_RE = re.compile(_NUMBER_RE)
_TIME_RE = re.compile(r"\b\d{1,2}:\d{2}\b")
_DATE_RE = re.compile(r"\b\d{1,2}[./-]\d{1,2}(?:[./-]\d{2,4})?\b")
_MIN_BARE_AMOUNT_MINOR = 10_000


@dataclass
class ParsedFreeTextExpense:
    amount_minor: int
    description: str | None


@router.message(StateFilter(None), F.text, ~F.text.startswith("/"))
async def on_free_text_expense_candidate(
    message: types.Message,
    freetext_drafts: FreeTextDraftStore,
    locale: str = "ru",
    request_id: str | None = None,
) -> None:
    parsed = _parse_freetext_expense(message.text or "")
    if parsed is None:
        return

    rid = _make_rid(request_id)
    await freetext_drafts.set(
        message.chat.id,
        rid,
        FreeTextDraft(amount_minor=parsed.amount_minor, description=parsed.description),
    )
    desc = parsed.description or ""
    await message.answer(
        t(
            "freetext.ask_confirm",
            locale,
            amount=format_amount(parsed.amount_minor, "RUB"),
            desc=desc,
        ),
        reply_markup=_confirm_keyboard(rid, locale),
    )


@router.callback_query(F.data.startswith("ft:save:"))
async def cb_save_free_text(
    query: types.CallbackQuery,
    freetext_drafts: FreeTextDraftStore,
    session_factory: Any,
    locale: str = "ru",
) -> None:
    rid = _rid(query)
    if rid is None or not query.from_user or not isinstance(query.message, types.Message):
        return

    chat_id = query.message.chat.id
    draft = await freetext_drafts.get(chat_id, rid)
    if draft is None:
        await query.answer()
        return

    async with session_factory() as session:
        user = await session.scalar(select(User).where(User.telegram_id == query.from_user.id))
        if not user:
            return
        ctx = await session.get(ActiveContext, user.id)
        if not ctx or not ctx.current_project_id:
            await query.answer()
            await query.message.answer(t("freetext.no_active", locale))
            return
        project = await session.get(Project, ctx.current_project_id)
        if not project:
            await query.answer()
            await query.message.answer(t("freetext.no_active", locale))
            return

        draft = await freetext_drafts.pop(chat_id, rid)
        if draft is None:
            await query.answer()
            return

        expense = Expense(
            project_id=project.id,
            amount_minor=draft.amount_minor,
            currency=project.currency,
            category="other",
            description=draft.description,
            paid_at=date.today(),
            created_by_user_id=user.id,
            source="bot_freetext",
        )
        session.add(expense)
        await session.commit()
        desc_line = (
            t("expenses.added_desc_line", locale, desc=draft.description)
            if draft.description
            else ""
        )
        response = t(
            "expenses.added",
            locale,
            amount=format_amount(draft.amount_minor, project.currency),
            category=label_for("other", locale),
            desc=desc_line,
        )

    try:
        await query.message.edit_reply_markup(reply_markup=None)
    except Exception:  # noqa: BLE001
        pass
    await query.message.answer(response)
    await query.answer()


@router.callback_query(F.data.startswith("ft:cancel:"))
async def cb_cancel_free_text(
    query: types.CallbackQuery,
    freetext_drafts: FreeTextDraftStore,
    locale: str = "ru",
) -> None:
    rid = _rid(query)
    if rid is None or not isinstance(query.message, types.Message):
        return
    await freetext_drafts.clear(query.message.chat.id, rid)
    try:
        await query.message.edit_reply_markup(reply_markup=None)
    except Exception:  # noqa: BLE001
        pass
    await query.message.answer(t("common.cancelled", locale))
    await query.answer()


def _parse_freetext_expense(text: str) -> ParsedFreeTextExpense | None:
    try:
        return _parse_with_patterns(text)
    except ValueError:
        return None


def _parse_with_patterns(text: str) -> ParsedFreeTextExpense:
    match = _PLUS_RE.search(text)
    if match:
        amount_minor = sum(
            parse_amount_to_minor(part.strip())
            for part in re.split(r"\s*\+\s*", match.group(0))
        )
        return ParsedFreeTextExpense(amount_minor, _description_without(text, match))

    match = _THOUSAND_RE.search(text)
    if match:
        number_match = _SIMPLE_RE.search(match.group(0))
        if number_match is None:
            raise ValueError("amount not found")
        amount_minor = parse_amount_to_minor(number_match.group(0)) * 1000
        return ParsedFreeTextExpense(amount_minor, _description_without(text, match))

    match = _CURRENCY_RE.search(text)
    if match:
        number_match = _SIMPLE_RE.search(match.group(0))
        if number_match is None:
            raise ValueError("amount not found")
        amount_minor = parse_amount_to_minor(number_match.group(0))
        return ParsedFreeTextExpense(amount_minor, _description_without(text, match))

    match = _last_bare_amount_match(text)
    if match is None:
        raise ValueError("amount not found")
    amount_minor = parse_amount_to_minor(match.group(0))
    return ParsedFreeTextExpense(amount_minor, _description_without(text, match))


def _description_without(text: str, match: re.Match[str]) -> str | None:
    description = (text[:match.start()] + text[match.end():]).strip()
    description = re.sub(r"\s+", " ", description)
    return description or None


def _last_bare_amount_match(text: str) -> re.Match[str] | None:
    ignored_spans = [
        *(match.span() for match in _TIME_RE.finditer(text)),
        *(match.span() for match in _DATE_RE.finditer(text)),
    ]
    for match in reversed(list(_SIMPLE_RE.finditer(text))):
        if any(match.start() < end and match.end() > start for start, end in ignored_spans):
            continue
        try:
            amount_minor = parse_amount_to_minor(match.group(0))
        except ValueError:
            continue
        if amount_minor >= _MIN_BARE_AMOUNT_MINOR:
            return match
    return None


def _confirm_keyboard(rid: str, locale: str = "ru") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t("freetext.save_button", locale), callback_data=f"ft:save:{rid}"),
        InlineKeyboardButton(text=t("freetext.cancel_button", locale), callback_data=f"ft:cancel:{rid}"),
    ]])


def _rid(query: types.CallbackQuery) -> str | None:
    if not query.data:
        return None
    parts = query.data.split(":", 2)
    if len(parts) != 3:
        return None
    return parts[2]


def _make_rid(request_id: str | None) -> str:
    source = request_id or uuid4().hex
    rid = re.sub(r"[^a-zA-Z0-9_-]", "", source)[:64]
    return rid or uuid4().hex
