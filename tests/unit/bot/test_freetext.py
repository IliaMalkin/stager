from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram import types

from packages.db.models import ActiveContext, Expense, Project, User


class FakeFreeTextDraftStore:
    def __init__(self) -> None:
        self.values: dict[tuple[int, str], object] = {}
        self.cleared: list[tuple[int, str]] = []

    async def set(self, chat_id: int, rid: str, draft: object) -> None:
        self.values[(chat_id, rid)] = draft

    async def get(self, chat_id: int, rid: str) -> object | None:
        return self.values.get((chat_id, rid))

    async def pop(self, chat_id: int, rid: str) -> object | None:
        value = self.values.pop((chat_id, rid), None)
        if value is not None:
            self.cleared.append((chat_id, rid))
        return value

    async def clear(self, chat_id: int, rid: str) -> None:
        self.cleared.append((chat_id, rid))
        self.values.pop((chat_id, rid), None)


def test_parse_freetext_amount_supports_thousands_suffix():
    from apps.bot.handlers.freetext import _parse_freetext_expense

    parsed = _parse_freetext_expense("Оплата рабочим первый этап 153 тыс")

    assert parsed is not None
    assert parsed.amount_minor == 15_300_000
    assert parsed.description == "Оплата рабочим первый этап"


def test_parse_freetext_amount_supports_plus_expression():
    from apps.bot.handlers.freetext import _parse_freetext_expense

    parsed = _parse_freetext_expense("Вентиляционные запчасти 4240+1424")

    assert parsed is not None
    assert parsed.amount_minor == 566_400
    assert parsed.description == "Вентиляционные запчасти"


@pytest.mark.parametrize("text", [
    "call at 14:00",
    "act 12",
    "2 days",
    "meeting 05.06.2026",
])
def test_parse_freetext_ignores_common_non_expense_numbers(text):
    from apps.bot.handlers.freetext import _parse_freetext_expense

    assert _parse_freetext_expense(text) is None


def test_parse_freetext_uses_last_simple_amount_candidate():
    from apps.bot.handlers.freetext import _parse_freetext_expense

    parsed = _parse_freetext_expense("bought 2 chairs for 5000")

    assert parsed is not None
    assert parsed.amount_minor == 500_000
    assert parsed.description == "bought 2 chairs for"


@pytest.mark.asyncio
async def test_free_text_amount_creates_confirmation_draft():
    from apps.bot.handlers.freetext import on_free_text_expense_candidate

    drafts = FakeFreeTextDraftStore()
    message = MagicMock(spec=types.Message)
    message.text = "5660 фитинги"
    message.chat = MagicMock(id=456)
    message.answer = AsyncMock()

    await on_free_text_expense_candidate(
        message,
        freetext_drafts=drafts,
        locale="ru",
        request_id="rid-1",
    )

    draft = drafts.values[(456, "rid-1")]
    assert draft.amount_minor == 566_000
    assert draft.description == "фитинги"
    reply_markup = message.answer.await_args.kwargs["reply_markup"]
    buttons = [button for row in reply_markup.inline_keyboard for button in row]
    assert [button.callback_data for button in buttons] == ["ft:save:rid-1", "ft:cancel:rid-1"]


@pytest.mark.asyncio
async def test_free_text_without_amount_is_silent():
    from apps.bot.handlers.freetext import on_free_text_expense_candidate

    message = MagicMock(spec=types.Message)
    message.text = "просто сообщение"
    message.chat = MagicMock(id=456)
    message.answer = AsyncMock()

    await on_free_text_expense_candidate(
        message,
        freetext_drafts=FakeFreeTextDraftStore(),
        locale="ru",
        request_id="rid-1",
    )

    message.answer.assert_not_awaited()


@pytest.mark.asyncio
async def test_free_text_save_writes_expense(fake_session_factory):
    from apps.bot.drafts import FreeTextDraft
    from apps.bot.handlers.freetext import cb_save_free_text

    session_factory, session = fake_session_factory
    drafts = FakeFreeTextDraftStore()
    drafts.values[(456, "rid-1")] = FreeTextDraft(
        amount_minor=15_300_000,
        description="Оплата рабочим первый этап",
    )
    user = User(id=10, telegram_id=123, full_name="Tester", role="user")
    project = Project(id=20, owner_user_id=10, name="Project", currency="RUB")
    session.scalars[User] = user
    session.by_model[ActiveContext][10] = ActiveContext(user_id=10, current_project_id=20)
    session.by_model[Project][20] = project

    query = MagicMock()
    query.data = "ft:save:rid-1"
    query.from_user = MagicMock(id=123)
    query.answer = AsyncMock()
    query.message = MagicMock(spec=types.Message)
    query.message.chat = MagicMock(id=456)
    query.message.edit_reply_markup = AsyncMock()
    query.message.answer = AsyncMock()

    await cb_save_free_text(
        query,
        freetext_drafts=drafts,
        session_factory=session_factory,
        locale="ru",
    )

    assert session.committed is True
    expense = next(item for item in session.added if isinstance(item, Expense))
    assert expense.amount_minor == 15_300_000
    assert expense.description == "Оплата рабочим первый этап"
    assert expense.category == "other"
    assert expense.source == "bot_freetext"
    assert drafts.cleared == [(456, "rid-1")]
    query.message.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_free_text_save_without_active_project_keeps_draft(fake_session_factory):
    from apps.bot.drafts import FreeTextDraft
    from apps.bot.handlers.freetext import cb_save_free_text

    session_factory, session = fake_session_factory
    drafts = FakeFreeTextDraftStore()
    drafts.values[(456, "rid-1")] = FreeTextDraft(amount_minor=100_000, description=None)
    session.scalars[User] = User(id=10, telegram_id=123, full_name="Tester", role="user")

    query = MagicMock()
    query.data = "ft:save:rid-1"
    query.from_user = MagicMock(id=123)
    query.answer = AsyncMock()
    query.message = MagicMock(spec=types.Message)
    query.message.chat = MagicMock(id=456)
    query.message.answer = AsyncMock()

    await cb_save_free_text(
        query,
        freetext_drafts=drafts,
        session_factory=session_factory,
        locale="ru",
    )

    assert session.committed is False
    assert drafts.cleared == []
    query.message.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_free_text_save_is_idempotent(fake_session_factory):
    from apps.bot.drafts import FreeTextDraft
    from apps.bot.handlers.freetext import cb_save_free_text

    session_factory, session = fake_session_factory
    drafts = FakeFreeTextDraftStore()
    drafts.values[(456, "rid-1")] = FreeTextDraft(amount_minor=100_000, description="paint")
    user = User(id=10, telegram_id=123, full_name="Tester", role="user")
    project = Project(id=20, owner_user_id=10, name="Project", currency="RUB")
    session.scalars[User] = user
    session.by_model[ActiveContext][10] = ActiveContext(user_id=10, current_project_id=20)
    session.by_model[Project][20] = project

    query = MagicMock()
    query.data = "ft:save:rid-1"
    query.from_user = MagicMock(id=123)
    query.answer = AsyncMock()
    query.message = MagicMock(spec=types.Message)
    query.message.chat = MagicMock(id=456)
    query.message.edit_reply_markup = AsyncMock()
    query.message.answer = AsyncMock()

    await cb_save_free_text(query, drafts, session_factory, locale="ru")
    await cb_save_free_text(query, drafts, session_factory, locale="ru")

    expenses = [item for item in session.added if isinstance(item, Expense)]
    assert len(expenses) == 1
