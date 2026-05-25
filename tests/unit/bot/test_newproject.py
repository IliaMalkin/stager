from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram import types

from packages.db.models import Project, User


@pytest.mark.asyncio
async def test_newproject_name_goes_straight_to_confirm():
    from apps.bot.fsm.states import NewProjectStates
    from apps.bot.handlers.projects import np_name

    message = MagicMock(spec=types.Message)
    message.text = "Квартира на Тверской"
    message.answer = AsyncMock()
    state = MagicMock()
    state.update_data = AsyncMock()
    state.set_state = AsyncMock()
    state.get_data = AsyncMock(return_value={"name": "Квартира на Тверской"})

    await np_name(message, state, locale="ru")

    state.update_data.assert_awaited_once_with(name="Квартира на Тверской")
    state.set_state.assert_awaited_once_with(NewProjectStates.confirm)
    message.answer.assert_awaited_once()
    assert "Бюджет" not in message.answer.await_args.args[0]


@pytest.mark.asyncio
async def test_newproject_name_ignores_commands():
    from apps.bot.handlers.projects import np_name

    message = MagicMock(spec=types.Message)
    message.text = "/list"
    message.answer = AsyncMock()
    state = MagicMock()
    state.update_data = AsyncMock()
    state.set_state = AsyncMock()

    await np_name(message, state, locale="ru")

    message.answer.assert_not_awaited()
    state.update_data.assert_not_awaited()
    state.set_state.assert_not_awaited()


@pytest.mark.asyncio
async def test_newproject_confirm_creates_project_without_budget(fake_session_factory):
    from apps.bot.handlers.projects import np_confirm_inline

    session_factory, session = fake_session_factory
    user = User(id=10, telegram_id=123, full_name="Tester", role="user", project_quota=None)
    session.scalars[User] = user

    query = MagicMock()
    query.from_user = MagicMock(id=123)
    query.answer = AsyncMock()
    query.message = MagicMock(spec=types.Message)
    query.message.edit_reply_markup = AsyncMock()
    query.message.answer = AsyncMock()
    state = MagicMock()
    state.get_data = AsyncMock(return_value={"name": "Квартира на Тверской"})
    state.clear = AsyncMock()

    await np_confirm_inline(
        query,
        state,
        session_factory=session_factory,
        locale="ru",
    )

    project = next(item for item in session.added if isinstance(item, Project))
    assert project.name == "Квартира на Тверской"
    assert project.budget_minor is None
    assert session.committed is True
    state.clear.assert_awaited_once()
