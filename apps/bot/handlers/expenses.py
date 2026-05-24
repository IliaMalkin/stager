"""/add — real implementation."""

from __future__ import annotations

from datetime import date

from aiogram import Router, types
from aiogram.filters import Command, CommandObject
from sqlalchemy import select

from apps.bot.i18n import t
from packages.db.base import async_session_factory
from packages.db.models import ActiveContext, Expense, Project, User
from packages.domain.categories import label_for
from packages.domain.currency import format_amount
from packages.domain.parsers import AddCommandParseError, parse_add_command

router = Router(name="expenses")


@router.message(Command("add"))
async def cmd_add(message: types.Message, command: CommandObject, locale: str = "ru") -> None:
    tg = message.from_user
    if not tg:
        return
    try:
        parsed = parse_add_command(command.args or "")
    except AddCommandParseError as exc:
        await message.answer(t("expenses.parse_error", locale, error=str(exc)))
        return

    async with async_session_factory() as session:
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
