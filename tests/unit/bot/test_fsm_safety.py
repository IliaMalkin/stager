from __future__ import annotations

import inspect
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram import types


def test_cancel_handler_is_registered_for_any_state():
    from apps.bot.handlers import start

    source = inspect.getsource(start)

    assert 'StateFilter("*")' in source
    assert '@router.message(Command("cancel"), StateFilter("*"))' in source


@pytest.mark.asyncio
async def test_cancel_handler_clears_state_and_answers():
    from apps.bot.handlers.start import cmd_cancel

    message = MagicMock(spec=types.Message)
    message.answer = AsyncMock()
    state = MagicMock()
    state.clear = AsyncMock()

    await cmd_cancel(message, state, locale="ru")

    state.clear.assert_awaited_once()
    message.answer.assert_awaited_once()


def test_redis_storage_has_fsm_ttl():
    from apps.bot import main

    source = inspect.getsource(main)

    assert "from datetime import timedelta" in source
    assert "state_ttl=timedelta(minutes=10)" in source
    assert "data_ttl=timedelta(minutes=10)" in source
