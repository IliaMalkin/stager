"""Smoke test: миграция накатывается, базовые insert/FK работают.

Запускается на CI с настоящим Postgres (через services), локально — тоже на настоящем
Postgres из docker-compose. Не используем sqlite — JSONB и FK с use_alter не работают.
"""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from packages.db.models import (
    ActiveContext, Expense, Invite, Project, ProjectMember, Receipt, User,
)


@pytest.fixture
async def session():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        pytest.skip("DATABASE_URL not set; run via docker compose or CI")
    engine = create_async_engine(db_url, pool_pre_ping=True, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
        await s.rollback()
    await engine.dispose()


async def test_user_project_expense_flow(session):
    user = User(telegram_id=999_001, full_name="Test", role="user")
    session.add(user)
    await session.flush()

    project = Project(owner_user_id=user.id, name="Тестовый проект", currency="RUB")
    session.add(project)
    await session.flush()

    session.add(ProjectMember(user_id=user.id, project_id=project.id, role="owner"))
    session.add(ActiveContext(user_id=user.id, current_project_id=project.id))

    receipt = Receipt(minio_key="receipts/test.jpg", ocr_status="ok")
    session.add(receipt)
    await session.flush()

    expense = Expense(
        project_id=project.id,
        amount_minor=485050,
        currency="RUB",
        category="furniture",
        description="диван",
        paid_at=date(2026, 5, 23),
        created_by_user_id=user.id,
        source="bot_photo",
        receipt_id=receipt.id,
        raw_ocr_json={"amount": 4850.50, "vendor": "ИКЕА"},
    )
    session.add(expense)
    await session.flush()
    receipt.expense_id = expense.id
    await session.flush()

    invite = Invite(
        token="test-token-001",
        issued_by_user_id=user.id,
        project_id=project.id,
        role="editor",
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    session.add(invite)
    await session.flush()

    # rollback в fixture'е, ничего не оставляем в БД
    assert expense.id > 0
    assert receipt.expense_id == expense.id
