from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram import types
from aiogram.filters import CommandObject

from packages.db.models import ActiveContext, Expense, Project, Receipt, User


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
async def test_cmd_expenses_lists_recent_expenses_with_delete_buttons(fake_session_factory):
    from apps.bot.handlers.expenses import cmd_expenses

    session_factory, session = fake_session_factory
    user = User(id=10, telegram_id=123, full_name="Tester", role="user")
    project = Project(id=20, owner_user_id=10, name="Project", currency="RUB")
    expense = Expense(
        id=30,
        project_id=20,
        amount_minor=485000,
        currency="RUB",
        category="furniture",
        description="диван",
        created_by_user_id=10,
        source="bot_text",
    )
    session.scalars[User] = user
    session.by_model[ActiveContext][10] = ActiveContext(user_id=10, current_project_id=20)
    session.by_model[Project][20] = project
    session.execute_rows = [expense]

    message = MagicMock(spec=types.Message)
    message.from_user = MagicMock(id=123)
    message.answer = AsyncMock()

    await cmd_expenses(message, session_factory=session_factory, locale="ru")

    args, kwargs = message.answer.await_args
    assert "Последние траты" in args[0]
    assert "диван" in args[0]
    keyboard = kwargs["reply_markup"]
    assert keyboard.inline_keyboard[0][0].callback_data == "exp:delete:30"


@pytest.mark.asyncio
async def test_delete_expense_asks_for_confirmation(fake_session_factory):
    from apps.bot.handlers.expenses import cb_delete_expense

    session_factory, session = fake_session_factory
    user = User(id=10, telegram_id=123, full_name="Tester", role="user")
    expense = Expense(
        id=30,
        project_id=20,
        amount_minor=485000,
        currency="RUB",
        category="furniture",
        description="диван",
        created_by_user_id=10,
        source="bot_text",
    )
    session.scalars[User] = user
    session.by_model[ActiveContext][10] = ActiveContext(user_id=10, current_project_id=20)
    session.by_model[Project][20] = Project(id=20, owner_user_id=10, name="Project", currency="RUB")
    session.by_model[Expense][30] = expense

    query = MagicMock(spec=types.CallbackQuery)
    query.from_user = MagicMock(id=123)
    query.data = "exp:delete:30"
    query.answer = AsyncMock()
    query.message = MagicMock(spec=types.Message)
    query.message.answer = AsyncMock()

    await cb_delete_expense(query, session_factory=session_factory, locale="ru")

    assert session.deleted == []
    args, kwargs = query.message.answer.await_args
    assert "Удалить трату" in args[0]
    assert kwargs["reply_markup"].inline_keyboard[0][0].callback_data == "exp:confirm_delete:30"


@pytest.mark.asyncio
async def test_confirm_delete_expense_deletes_active_project_expense_and_unlinks_receipt(fake_session_factory):
    from apps.bot.handlers.expenses import cb_confirm_delete_expense

    session_factory, session = fake_session_factory
    user = User(id=10, telegram_id=123, full_name="Tester", role="user")
    expense = Expense(
        id=30,
        project_id=20,
        amount_minor=485000,
        currency="RUB",
        category="furniture",
        description="диван",
        receipt_id=40,
        created_by_user_id=10,
        source="receipt",
    )
    receipt = Receipt(
        id=40,
        minio_key="receipts/20/file.jpg",
        ocr_status="saved",
        expense_id=30,
    )
    session.scalars[User] = user
    session.by_model[ActiveContext][10] = ActiveContext(user_id=10, current_project_id=20)
    session.by_model[Project][20] = Project(id=20, owner_user_id=10, name="Project", currency="RUB")
    session.by_model[Expense][30] = expense
    session.by_model[Receipt][40] = receipt

    query = MagicMock(spec=types.CallbackQuery)
    query.from_user = MagicMock(id=123)
    query.data = "exp:confirm_delete:30"
    query.answer = AsyncMock()
    query.message = MagicMock(spec=types.Message)
    query.message.edit_reply_markup = AsyncMock()
    query.message.answer = AsyncMock()

    await cb_confirm_delete_expense(query, session_factory=session_factory, locale="ru")

    assert session.deleted == [expense]
    assert receipt.expense_id is None
    assert session.committed is True
    query.message.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_confirm_delete_expense_rejects_non_active_project_expense(fake_session_factory):
    from apps.bot.handlers.expenses import cb_confirm_delete_expense

    session_factory, session = fake_session_factory
    user = User(id=10, telegram_id=123, full_name="Tester", role="user")
    expense = Expense(
        id=30,
        project_id=99,
        amount_minor=485000,
        currency="RUB",
        category="furniture",
        description="диван",
        created_by_user_id=10,
        source="bot_text",
    )
    session.scalars[User] = user
    session.by_model[ActiveContext][10] = ActiveContext(user_id=10, current_project_id=20)
    session.by_model[Expense][30] = expense

    query = MagicMock(spec=types.CallbackQuery)
    query.from_user = MagicMock(id=123)
    query.data = "exp:confirm_delete:30"
    query.answer = AsyncMock()
    query.message = MagicMock(spec=types.Message)

    await cb_confirm_delete_expense(query, session_factory=session_factory, locale="ru")

    assert session.deleted == []
    assert session.committed is False
    query.answer.assert_awaited_once()


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
