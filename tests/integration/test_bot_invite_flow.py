"""End-to-end invite redeem: create invite via API → /start <token> в боте → user в БД, член проекта.

Не поднимаем aiogram целиком — дёргаем handler напрямую с мок-message, реальную БД используем.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.bot.handlers.start import _redeem_invite
from packages.db.models import Invite, Project, ProjectMember, User

@pytest.fixture
async def db_engine():
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not set")
    engine = create_async_engine(url)
    yield engine
    await engine.dispose()


@pytest.fixture
async def fixtures(db_engine):
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as s:
        owner = User(telegram_id=111_222_333, full_name="Owner", role="admin")
        s.add(owner)
        await s.flush()
        project = Project(owner_user_id=owner.id, name="Invite test", currency="RUB")
        s.add(project)
        await s.flush()
        s.add(ProjectMember(user_id=owner.id, project_id=project.id, role="owner"))
        invite = Invite(
            token="testinvite12345",
            issued_by_user_id=owner.id,
            project_id=project.id,
            role="editor",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )
        s.add(invite)
        await s.commit()
        yield {"owner": owner, "project": project, "invite": invite}
        # cleanup
        async with factory() as ss:
            await ss.execute(
                ProjectMember.__table__.delete().where(ProjectMember.project_id == project.id)
            )
            inv = await ss.scalar(select(Invite).where(Invite.token == "testinvite12345"))
            if inv:
                await ss.delete(inv)
            proj = await ss.get(Project, project.id)
            if proj:
                await ss.delete(proj)
            o = await ss.get(User, owner.id)
            if o:
                await ss.delete(o)
            await ss.commit()


def _mk_message(tg_id: int, username: str = "bob") -> MagicMock:
    msg = MagicMock()
    msg.from_user = MagicMock(id=tg_id, username=username, full_name="Bob")
    msg.answer = AsyncMock()
    return msg


async def test_redeem_invite_creates_user_and_member(db_engine, fixtures):
    msg = _mk_message(tg_id=444_555_666)
    await _redeem_invite(msg, "testinvite12345")

    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as s:
        user = await s.scalar(select(User).where(User.telegram_id == 444_555_666))
        assert user is not None
        assert user.role == "user"

        member = await s.scalar(
            select(ProjectMember).where(
                ProjectMember.user_id == user.id,
                ProjectMember.project_id == fixtures["project"].id,
            )
        )
        assert member is not None
        assert member.role == "editor"

        invite = await s.scalar(select(Invite).where(Invite.token == "testinvite12345"))
        assert invite is not None
        assert invite.used_by_user_id == user.id
        assert invite.used_at is not None

        # cleanup
        await s.delete(member)
        await s.delete(user)
        await s.commit()
    msg.answer.assert_awaited()


async def test_redeem_expired_invite_rejected(db_engine, fixtures):
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as s:
        owner = fixtures["owner"]
        expired = Invite(
            token="expiredinvite",
            issued_by_user_id=owner.id,
            project_id=fixtures["project"].id,
            role="editor",
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        s.add(expired)
        await s.commit()

    msg = _mk_message(tg_id=777_888_999)
    await _redeem_invite(msg, "expiredinvite")
    msg.answer.assert_awaited_once()
    # сообщение пользователю содержит "истёк"
    args = msg.answer.await_args
    assert "истёк" in args.args[0]

    # пользователь НЕ создан
    async with factory() as s:
        user = await s.scalar(select(User).where(User.telegram_id == 777_888_999))
        assert user is None

        ex = await s.scalar(select(Invite).where(Invite.token == "expiredinvite"))
        if ex:
            await s.delete(ex)
        await s.commit()


async def test_redeem_unknown_token(db_engine, fixtures):
    msg = _mk_message(tg_id=999_000_111)
    await _redeem_invite(msg, "nonexistent")
    msg.answer.assert_awaited_once()
    args = msg.answer.await_args
    assert "не найден" in args.args[0]
