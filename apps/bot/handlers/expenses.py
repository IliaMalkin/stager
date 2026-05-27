"""/add — real implementation."""

from __future__ import annotations

from html import escape
from datetime import date
from typing import Any

from aiogram import F, Router, types
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from sqlalchemy import select

from apps.bot.fsm.states import AddExpenseStates
from apps.bot.i18n import t
from apps.bot.keyboards import (
    add_category_picker_keyboard,
    expense_delete_confirm_keyboard,
    expenses_list_keyboard,
)
from packages.db.models import ActiveContext, Expense, Project, Receipt, User
from packages.domain.categories import Category, label_for, parse_category
from packages.domain.currency import format_amount, parse_amount_to_minor
from packages.domain.parsers import AddCommandParseError, parse_add_command

router = Router(name="expenses")


@router.message(Command("expenses"))
async def cmd_expenses(message: types.Message, session_factory: Any, locale: str = "ru") -> None:
    tg = message.from_user
    if not tg:
        return

    async with session_factory() as session:
        _user, project = await _active_project_for_user(session, tg.id)
        if not project:
            await message.answer(t("projects.no_active", locale))
            return

        result = await session.execute(
            select(Expense)
            .where(Expense.project_id == project.id)
            .order_by(Expense.paid_at.desc(), Expense.id.desc())
            .limit(5)
        )
        expenses = list(result.scalars().all())
        if not expenses:
            await message.answer("В активном проекте пока нет трат.")
            return

        lines = [_format_expense_line(expense, locale) for expense in expenses]
        await message.answer(
            f"Последние траты в <b>{escape(project.name)}</b>:\n\n" + "\n\n".join(lines),
            reply_markup=expenses_list_keyboard(expenses),
        )


@router.callback_query(F.data.startswith("exp:delete:"))
async def cb_delete_expense(query: types.CallbackQuery, session_factory: Any, locale: str = "ru") -> None:
    expense_id = _expense_id_from_callback(query.data)
    if expense_id is None:
        await query.answer()
        return

    expense = await _get_active_project_expense(session_factory, query.from_user.id, expense_id)
    if not expense:
        await query.answer("Трата не найдена в активном проекте.", show_alert=True)
        return

    await query.answer()
    if query.message:
        await query.message.answer(
            "Удалить трату?\n\n" + _format_expense_line(expense, locale),
            reply_markup=expense_delete_confirm_keyboard(expense.id),
        )


@router.callback_query(F.data.startswith("exp:confirm_delete:"))
async def cb_confirm_delete_expense(
    query: types.CallbackQuery,
    session_factory: Any,
    locale: str = "ru",
) -> None:
    expense_id = _expense_id_from_callback(query.data)
    if expense_id is None:
        await query.answer()
        return

    async with session_factory() as session:
        _user, project = await _active_project_for_user(session, query.from_user.id)
        expense = await session.get(Expense, expense_id)
        if not project or not expense or expense.project_id != project.id:
            await query.answer("Трата не найдена в активном проекте.", show_alert=True)
            return

        if expense.receipt_id:
            receipt = await session.get(Receipt, expense.receipt_id)
            if receipt:
                receipt.expense_id = None
        await session.delete(expense)
        await session.commit()

    await query.answer()
    if query.message:
        try:
            await query.message.edit_reply_markup(reply_markup=None)
        except Exception:  # noqa: BLE001
            pass
        await query.message.answer("Удалено.")


@router.callback_query(F.data.startswith("exp:cancel_delete:"))
async def cb_cancel_delete_expense(query: types.CallbackQuery) -> None:
    await query.answer("Отменено.")
    if query.message:
        try:
            await query.message.edit_reply_markup(reply_markup=None)
        except Exception:  # noqa: BLE001
            pass


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
        _user, project = await _active_project_for_user(session, telegram_id)
        return project is not None


async def _active_project_for_user(session: Any, telegram_id: int) -> tuple[User | None, Project | None]:
    user = await session.scalar(select(User).where(User.telegram_id == telegram_id))
    if not user:
        return None, None
    ctx = await session.get(ActiveContext, user.id)
    if not ctx or not ctx.current_project_id:
        return user, None
    project = await session.get(Project, ctx.current_project_id)
    return user, project


async def _get_active_project_expense(session_factory: Any, telegram_id: int, expense_id: int) -> Expense | None:
    async with session_factory() as session:
        _user, project = await _active_project_for_user(session, telegram_id)
        expense = await session.get(Expense, expense_id)
        if not project or not expense or expense.project_id != project.id:
            return None
        return expense


def _expense_id_from_callback(callback_data: str | None) -> int | None:
    if not callback_data:
        return None
    try:
        return int(callback_data.rsplit(":", maxsplit=1)[-1])
    except ValueError:
        return None


def _format_expense_line(expense: Expense, locale: str) -> str:
    paid_at = expense.paid_at.isoformat() if expense.paid_at else "без даты"
    description = f"\n{escape(expense.description)}" if expense.description else ""
    return (
        f"#{expense.id} · {format_amount(expense.amount_minor, expense.currency)} · "
        f"{escape(label_for(expense.category, locale))} · {paid_at}"
        f"{description}"
    )


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
