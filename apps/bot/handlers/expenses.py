"""/add — real implementation."""

from __future__ import annotations

from datetime import date
from typing import Any

from aiogram import F, Router, types
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from sqlalchemy import select

from apps.bot.fsm.states import AddExpenseStates
from apps.bot.i18n import t
from apps.bot.keyboards import add_category_picker_keyboard
from packages.db.models import ActiveContext, Expense, Project, User
from packages.domain.categories import Category, label_for, parse_category
from packages.domain.currency import format_amount, parse_amount_to_minor
from packages.domain.parsers import AddCommandParseError, parse_add_command

router = Router(name="expenses")


@router.message(Command("add"))
async def cmd_add(
    message: types.Message,
    command: CommandObject,
    state: FSMContext,
    session_factory: Any,
    locale: str = "ru",
) -> None:
    tg = message.from_user
    if not tg:
        return
    await state.clear()
    if not (command.args or "").strip():
        if not await _has_active_project(session_factory, tg.id):
            await message.answer(t("projects.no_active", locale))
            return
        await state.set_state(AddExpenseStates.amount)
        await message.answer(t("expenses.dialog.ask_amount", locale))
        return

    try:
        parsed = parse_add_command(command.args or "")
    except AddCommandParseError as exc:
        await message.answer(t("expenses.parse_error", locale, error=str(exc)))
        return

    async with session_factory() as session:
        user = await session.scalar(select(User).where(User.telegram_id == tg.id))
        if not user:
            return
        ctx = await session.get(ActiveContext, user.id)
        if not ctx or not ctx.current_project_id:
            await message.answer(t("projects.no_active", locale))
            return
        project = await session.get(Project, ctx.current_project_id)
        if not project:
            await message.answer(t("projects.no_active", locale))
            return
        expense = Expense(
            project_id=project.id,
            amount_minor=parsed.amount_minor,
            currency=project.currency,
            category=parsed.category,
            description=parsed.description,
            paid_at=date.today(),
            created_by_user_id=user.id,
            source="bot_text",
        )
        session.add(expense)
        await session.commit()
        desc_line = (
            t("expenses.added_desc_line", locale, desc=parsed.description)
            if parsed.description
            else ""
        )
        await message.answer(t(
            "expenses.added",
            locale,
            amount=format_amount(parsed.amount_minor, project.currency),
            category=label_for(parsed.category, locale),
            desc=desc_line,
        ))


@router.message(AddExpenseStates.amount, F.text, ~F.text.startswith("/"))
async def add_amount_input(message: types.Message, state: FSMContext, locale: str = "ru") -> None:
    if (message.text or "").startswith("/"):
        return
    try:
        amount_minor = parse_amount_to_minor(message.text or "")
    except ValueError:
        await message.answer(t("expenses.dialog.bad_amount", locale))
        return
    await state.update_data(amount_minor=amount_minor)
    await state.set_state(AddExpenseStates.category)
    await message.answer(
        t("expenses.dialog.ask_category", locale),
        reply_markup=add_category_picker_keyboard(locale),
    )


@router.callback_query(AddExpenseStates.category, F.data.startswith("add:cat:"))
async def add_category_selected(
    query: types.CallbackQuery,
    state: FSMContext,
    locale: str = "ru",
) -> None:
    if not query.data:
        return
    raw_category = query.data.removeprefix("add:cat:")
    category = "other" if raw_category == "skip" else parse_category(raw_category)
    if category is None:
        await query.answer()
        return
    await state.update_data(category=category)
    await state.set_state(AddExpenseStates.description)
    await query.answer()
    if isinstance(query.message, types.Message):
        try:
            await query.message.edit_reply_markup(reply_markup=None)
        except Exception:  # noqa: BLE001
            pass
        await query.message.answer(
            f"{t('expenses.dialog.ask_description', locale)}\n"
            f"{t('expenses.dialog.skip_hint', locale)}"
        )


@router.message(AddExpenseStates.description, Command("skip"))
async def add_description_skip(
    message: types.Message,
    state: FSMContext,
    session_factory: Any,
    locale: str = "ru",
) -> None:
    await _save_dialog_expense(message, state, session_factory, locale, description=None)


@router.message(AddExpenseStates.description, F.text, ~F.text.startswith("/"))
async def add_description_input(
    message: types.Message,
    state: FSMContext,
    session_factory: Any,
    locale: str = "ru",
) -> None:
    if (message.text or "").startswith("/"):
        return
    description = (message.text or "").strip() or None
    await _save_dialog_expense(message, state, session_factory, locale, description=description)


async def _has_active_project(session_factory: Any, telegram_id: int) -> bool:
    async with session_factory() as session:
        user = await session.scalar(select(User).where(User.telegram_id == telegram_id))
        if not user:
            return False
        ctx = await session.get(ActiveContext, user.id)
        if not ctx or not ctx.current_project_id:
            return False
        project = await session.get(Project, ctx.current_project_id)
        return project is not None


async def _save_dialog_expense(
    message: types.Message,
    state: FSMContext,
    session_factory: Any,
    locale: str,
    *,
    description: str | None,
) -> None:
    tg = message.from_user
    if not tg:
        return
    data = await state.get_data()
    amount_minor = data.get("amount_minor")
    category: Category = data.get("category", "other")
    if amount_minor is None:
        await state.clear()
        return

    async with session_factory() as session:
        user = await session.scalar(select(User).where(User.telegram_id == tg.id))
        if not user:
            await state.clear()
            return
        ctx = await session.get(ActiveContext, user.id)
        if not ctx or not ctx.current_project_id:
            await state.clear()
            await message.answer(t("projects.no_active", locale))
            return
        project = await session.get(Project, ctx.current_project_id)
        if not project:
            await state.clear()
            await message.answer(t("projects.no_active", locale))
            return
        expense = Expense(
            project_id=project.id,
            amount_minor=amount_minor,
            currency=project.currency,
            category=category,
            description=description,
            paid_at=date.today(),
            created_by_user_id=user.id,
            source="bot_text",
        )
        session.add(expense)
        await session.commit()
        desc_line = (
            t("expenses.added_desc_line", locale, desc=description)
            if description
            else ""
        )
        response = t(
            "expenses.added",
            locale,
            amount=format_amount(amount_minor, project.currency),
            category=label_for(category, locale),
            desc=desc_line,
        )

    await state.clear()
    await message.answer(response)
