"""/invite — owner-only. Опциональный аргумент: лимит проектов для приглашённого.

Использование:
    /invite           — приглашение в активный проект как editor, без квоты создания
    /invite 3         — то же + redeemer сможет создать СВОИХ 3 проекта (для ассистентов)
    /invite quota 5   — quota-only invite (НЕ привязан к проекту, только право создавать 5)
"""

from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from aiogram import Bot, Router, types
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from sqlalchemy import select

from apps.bot.i18n import t
from packages.db.models import ActiveContext, Invite, ProjectMember, User

router = Router(name="invites")

_DEFAULT_TTL_HOURS = 48


def _parse_args(raw: str) -> tuple[bool, int | None]:
    """Возвращает (quota_only, max_projects). Поддерживает форматы:
    ""           → (False, None)
    "3"          → (False, 3)
    "quota 5"    → (True, 5)
    """
    parts = (raw or "").strip().split()
    if not parts:
        return False, None
    if len(parts) >= 2 and parts[0].lower() in ("quota", "квота"):
        try:
            return True, max(0, int(parts[1]))
        except ValueError:
            return False, None
    try:
        return False, max(0, int(parts[0]))
    except ValueError:
        return False, None


@router.message(Command("invite"))
async def cmd_invite(
    message: types.Message,
    command: CommandObject,
    bot: Bot,
    session_factory: Any,
    locale: str = "ru",
    state: FSMContext | None = None,
) -> None:
    if state is not None:
        await state.clear()
    tg = message.from_user
    if not tg:
        return

    quota_only, max_projects = _parse_args(command.args or "")

    async with session_factory() as session:
        user = await session.scalar(select(User).where(User.telegram_id == tg.id))
        if not user:
            return
        target_project_id: int | None = None
        if not quota_only:
            ctx = await session.get(ActiveContext, user.id)
            if not ctx or not ctx.current_project_id:
                await message.answer(t("invite.no_active", locale))
                return
            member = await session.scalar(
                select(ProjectMember).where(
                    ProjectMember.user_id == user.id,
                    ProjectMember.project_id == ctx.current_project_id,
                )
            )
            if not member or member.role != "owner":
                await message.answer(t("invite.not_owner", locale))
                return
            target_project_id = ctx.current_project_id

        token = secrets.token_urlsafe(24)[:48]
        expires = datetime.now(timezone.utc) + timedelta(hours=_DEFAULT_TTL_HOURS)
        invite = Invite(
            token=token,
            issued_by_user_id=user.id,
            project_id=target_project_id,
            role="editor",
            max_projects=max_projects,
            expires_at=expires,
        )
        session.add(invite)
        await session.commit()

    bot_username = os.getenv("TELEGRAM_BOT_USERNAME") or (await bot.get_me()).username
    url = f"https://t.me/{bot_username}?start={token}"
    quota_line = f"\nЛимит создания проектов: {max_projects}" if max_projects is not None else ""
    scope_line = (
        "Только право создавать СВОИ проекты, без членства."
        if quota_only
        else "Будет добавлен в активный проект как editor."
    )
    await message.answer(
        f"🔗 Инвайт готов (действует {_DEFAULT_TTL_HOURS}ч):\n\n{url}\n\n{scope_line}{quota_line}"
    )
