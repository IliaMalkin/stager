"""Bot middlewares: tracing, auth (whitelist + DB lookup) и i18n.

ВАЖНО про уровни в aiogram 3:
- `dp.update.middleware(...)` принимает Update — на этом уровне `event` это `Update`,
  не Message, и data ещё не содержит `event_message`. Auth-логика, основанная на
  `from_user`, не работает.
- Поэтому мы подключаемся через `dp.message.outer_middleware(...)` и
  `dp.callback_query.outer_middleware(...)` — там event это уже Message/CallbackQuery
  с готовым `from_user`.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable

import structlog
from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject
from sqlalchemy import select

from packages.db.base import get_sessionmaker
from packages.db.models import User
from packages.observability import bind_request_id, clear_request_id

log = structlog.get_logger(__name__)


class TracingMiddleware(BaseMiddleware):
    """Generates a request_id for every update and binds it to structlog contextvars."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        rid = bind_request_id()
        data["request_id"] = rid
        try:
            return await handler(event, data)
        finally:
            clear_request_id()


class AuthMiddleware(BaseMiddleware):
    """Reject users who are neither in whitelist nor have a User record."""

    def __init__(self, whitelist: set[int]) -> None:
        self.whitelist = whitelist

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user_id: int | None = None
        text: str = ""
        responder: Message | None = None

        if isinstance(event, Message) and event.from_user:
            tg_user_id = event.from_user.id
            text = event.text or ""
            responder = event
        elif isinstance(event, CallbackQuery) and event.from_user:
            tg_user_id = event.from_user.id
            responder = event.message if isinstance(event.message, Message) else None
        else:
            return await handler(event, data)

        if tg_user_id is None:
            return await handler(event, data)

        # Whitelist passes immediately
        if tg_user_id in self.whitelist:
            return await handler(event, data)

        # /start (with or without token) passes — start handler will decide
        if text.startswith("/start"):
            return await handler(event, data)

        async with get_sessionmaker()() as session:
            user = await session.scalar(select(User).where(User.telegram_id == tg_user_id))
        if user:
            data["current_user"] = user
            return await handler(event, data)

        log.info("bot.auth_rejected", tg_id=tg_user_id, kind=type(event).__name__)
        if isinstance(event, CallbackQuery):
            await event.answer("Бот закрытый. Нужен инвайт.", show_alert=True)
        elif responder:
            await responder.answer("Бот закрытый. Нужен инвайт — попроси у владельца.")
        return None


class I18nMiddleware(BaseMiddleware):
    """Sets data['locale'] from user.locale or default."""

    def __init__(self, default_locale: str = "ru") -> None:
        self.default_locale = default_locale

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user: User | None = data.get("current_user")
        data["locale"] = (user.locale if user else None) or self.default_locale
        return await handler(event, data)
