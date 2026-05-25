from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram import types

from apps.bot.drafts import Draft
from packages.db.models import ActiveContext, Project, Receipt, User


@pytest.mark.asyncio
async def test_cb_save_uses_injected_resources(monkeypatch, fake_session_factory, fake_drafts):
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/15")
    from apps.bot.handlers.photo import cb_save

    session_factory, session = fake_session_factory
    user = User(id=10, telegram_id=123, full_name="Tester", role="user")
    project = Project(id=20, owner_user_id=10, name="DI project", currency="RUB")
    receipt = Receipt(id=30, minio_key="receipts/30.jpg", ocr_status="ok")

    session.scalars[User] = user
    session.by_model[ActiveContext][10] = ActiveContext(user_id=10, current_project_id=20)
    session.by_model[Project][20] = project
    session.by_model[Receipt][30] = receipt
    fake_drafts.values[30] = Draft(
        amount=123.45,
        currency="RUB",
        vendor="Store",
        date=date(2026, 5, 25).isoformat(),
        category="other",
    )

    query = MagicMock()
    query.data = "rcpt:save:30"
    query.from_user = MagicMock(id=123)
    query.answer = AsyncMock()
    query.message = MagicMock(spec=types.Message)
    query.message.edit_reply_markup = AsyncMock()
    query.message.answer = AsyncMock()

    await cb_save(
        query,
        session_factory=session_factory,
        drafts=fake_drafts,
        locale="ru",
    )

    assert session.committed is True
    assert receipt.expense_id == session.added[0].id
    assert fake_drafts.cleared == [30]
    query.message.answer.assert_awaited()
