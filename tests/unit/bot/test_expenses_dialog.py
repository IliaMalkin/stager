from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram import types
from aiogram.filters import CommandObject

from packages.db.models import ActiveContext, Expense, Project, User


@pytest.mark.asyncio
async def test_cmd_add_without_args_starts_dialog(fake_session_factory):
    from apps.bot.fsm.states import AddExpenseStates
    from apps.bot.handlers.expenses import cmd_add

    message = MagicMock(spec=types.Message)
    message.from_user = MagicMock(id=123)
    message.answer = AsyncMock()
    state = MagicMock()
    state.clear = AsyncMock()
    state.set_state = AsyncMock()
    session_factory, session = fake_session_factory
    user = User(id=10, telegram_id=123, full_name="Tester", role="user")
    project = Project(id=20, owner_user_id=10, name="Project", currency="RUB")
    session.scalars[User] = user
    session.by_model[ActiveContext][10] = ActiveContext(user_id=10, current_project_id=20)
    session.by_model[Project][20] = project

    await cmd_add(
        message,
        CommandObject(prefix="/", command="add", mention=None, args=None),
        state=state,
        session_factory=session_factory,
        locale="ru",
    )

    state.clear.assert_awaited_once()
    state.set_state.assert_awaited_once_with(AddExpenseStates.amount)
    message.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_cmd_add_without_args_requires_active_project(fake_session_factory):
    from apps.bot.handlers.expenses import cmd_add

    session_factory, session = fake_session_factory
    session.scalars[User] = User(id=10, telegram_id=123, full_name="Tester", role="user")
    message = MagicMock(spec=types.Message)
    message.from_user = MagicMock(id=123)
    message.answer = AsyncMock()
    state = MagicMock()
    state.clear = AsyncMock()
    state.set_state = AsyncMock()

    await cmd_add(
        message,
        CommandObject(prefix="/", command="add", mention=None, args=None),
        state=state,
        session_factory=session_factory,
        locale="ru",
    )

    state.clear.assert_awaited_once()
    state.set_state.assert_not_awaited()
    message.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_add_amount_ignores_commands():
    from apps.bot.handlers.expenses import add_amount_input

    message = MagicMock(spec=types.Message)
    message.text = "/list"
    message.answer = AsyncMock()
    state = MagicMock()
    state.update_data = AsyncMock()
    state.set_state = AsyncMock()

    await add_amount_input(message, state, locale="ru")

    message.answer.assert_not_awaited()
    state.update_data.assert_not_awaited()
    state.set_state.assert_not_awaited()


@pytest.mark.asyncio
async def test_add_category_callback_moves_to_description():
    from apps.bot.fsm.states import AddExpenseStates
    from apps.bot.handlers.expenses import add_category_selected

    query = MagicMock()
    query.data = "add:cat:furniture"
    query.answer = AsyncMock()
    query.message = MagicMock(spec=types.Message)
    query.message.edit_reply_markup = AsyncMock()
    query.message.answer = AsyncMock()
    state = MagicMock()
    state.update_data = AsyncMock()
    state.set_state = AsyncMock()

    await add_category_selected(query, state, locale="ru")

    state.update_data.assert_awaited_once_with(category="furniture")
    state.set_state.assert_awaited_once_with(AddExpenseStates.description)
    query.message.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_add_description_saves_expense(fake_session_factory):
    from apps.bot.handlers.expenses import add_description_input

    session_factory, session = fake_session_factory
    user = User(id=10, telegram_id=123, full_name="Tester", role="user")
    project = Project(id=20, owner_user_id=10, name="Project", currency="RUB")
    session.scalars[User] = user
    session.by_model[ActiveContext][10] = ActiveContext(user_id=10, current_project_id=20)
    session.by_model[Project][20] = project

    message = MagicMock(spec=types.Message)
    message.from_user = MagicMock(id=123)
    message.text = "диван"
    message.answer = AsyncMock()
    state = MagicMock()
    state.get_data = AsyncMock(return_value={"amount_minor": 485000, "category": "furniture"})
    state.clear = AsyncMock()

    await add_description_input(
        message,
        state,
        session_factory=session_factory,
        locale="ru",
    )

    assert session.committed is True
    expense = next(item for item in session.added if isinstance(item, Expense))
    assert expense.amount_minor == 485000
    assert expense.category == "furniture"
    assert expense.description == "диван"
    state.clear.assert_awaited_once()
    message.answer.assert_awaited_once()
