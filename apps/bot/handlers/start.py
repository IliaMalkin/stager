"""/start, /help, /cancel handlers."""

from __future__ import annotations

import os
from datetime import datetime, timezone

from aiogram import Router, types
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from sqlalchemy import select

from apps.bot.i18n import t
from packages.db.base import async_session_factory
from packages.db.models import Invite, ProjectMember, User


def _whitelist() -> set[int]:
    raw = os.getenv("TELEGRAM_WHITELIST_IDS", "")
    return {int(x) for x in raw.split(",") if x.strip().isdigit()}

router = Router(name="start")


@router.message(CommandStart(deep_link=True))
async def cmd_start_with_token(message: types.Message, command: CommandObject) -> None:
    token = (command.args or "").strip()
    if not token:
        await _greet(message)
        return
    await _redeem_invite(message, token)


@router.message(CommandStart())
async def cmd_start_plain(message: types.Message) -> None:
    await _greet(message)


@router.message(Command("help"))
async def cmd_help(message: types.Message, locale: str = "ru") -> None:
    await message.answer(t("help.text", locale))


@router.message(Command("cancel"))
async def cmd_cancel(message: types.Message, state: FSMContext, locale: str = "ru") -> None:
    await state.clear()
    await message.answer(t("common.cancelled", locale))


async def _greet(message: types.Message) -> None:
    tg = message.from_user
    if not tg:
        return
    async with async_session_factory() as session:
        user = await session.scalar(select(User).where(User.telegram_id == tg.id))
        if user:
            await message.answer(t("start.welcome_back", user.locale or "ru"))
            return
        # КРИТИЧНО: /start без invite-токена — это попытка зайти как owner.
        # Только whitelist'еные id (env TELEGRAM_WHITELIST_IDS) могут так делать.
        # Все остальные обязаны прийти с /start <invite_token>.
        if tg.id not in _whitelist():
            await message.answer(t("start.auth_rejected", "ru"))
            return
        user = User(
            telegram_id=tg.id,
            username=tg.username,
            full_name=tg.full_name,
            role="admin",
        )
        session.add(user)
        await session.commit()
        locale = user.locale or "ru"
    await message.answer(t("start.welcome_new", locale))


async def _redeem_invite(message: types.Message, token: str) -> None:
    tg = message.from_user
    if not tg:
        return
    async with async_session_factory() as session:
        invite = await session.scalar(select(Invite).where(Invite.token == token))
        if not invite:
            await message.answer(t("start.invite_not_found", "ru"))
            return
        if invite.used_at is not None:
            await message.answer(t("start.invite_used", "ru"))
            return
        if invite.expires_at < datetime.now(timezone.utc):
            await message.answer(t("start.invite_expired", "ru"))
            return

        user = await session.scalar(select(User).where(User.telegram_id == tg.id))
        if not user:
            user = User(
                telegram_id=tg.id,
                username=tg.username,
                full_name=tg.full_name,
                role="user",
                # Квота копируется только при первой регистрации через invite.
                # Whitelist-юзеры (создаются в _greet) получают NULL = unlimited.
                project_quota=invite.max_projects,
            )
            session.add(user)
            await session.flush()

        if invite.project_id:
            exists = await session.scalar(
                select(ProjectMember).where(
                    ProjectMember.user_id == user.id,
                    ProjectMember.project_id == invite.project_id,
                )
            )
            if not exists:
                session.add(ProjectMember(
                    user_id=user.id, project_id=invite.project_id, role=invite.role,
                ))

        invite.used_by_user_id = user.id
        invite.used_at = datetime.now(timezone.utc)
        await session.commit()

    await message.answer(t("start.invite_redeemed", "ru"))
