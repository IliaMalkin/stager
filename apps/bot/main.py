"""Stager Telegram bot — entry point.

Run locally: `python -m apps.bot.main`
Run in compose: `docker compose up bot`
"""

from __future__ import annotations

import asyncio
import os

import structlog
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import BotCommand, BotCommandScopeAllPrivateChats, BotCommandScopeDefault
from redis.asyncio import Redis

from apps.bot.handlers import expenses, invites, photo, projects, report, start
from apps.bot.middlewares import AuthMiddleware, I18nMiddleware, TracingMiddleware
from packages.observability import configure_logging, init_sentry

log = structlog.get_logger(__name__)


def _whitelist() -> set[int]:
    raw = os.getenv("TELEGRAM_WHITELIST_IDS", "")
    return {int(x) for x in raw.split(",") if x.strip().isdigit()}


_COMMANDS_RU = [
    BotCommand(command="newproject", description="📁 Создать проект"),
    BotCommand(command="list",       description="📋 Мои проекты"),
    BotCommand(command="switch",     description="🔁 Переключить активный"),
    BotCommand(command="add",        description="✍️ Записать трату текстом"),
    BotCommand(command="report",     description="📊 Отчёт по активному проекту"),
    BotCommand(command="invite",     description="🔗 Пригласить в проект"),
    BotCommand(command="help",       description="❓ Справка"),
    BotCommand(command="cancel",     description="🚪 Выйти из диалога"),
]

_SHORT_DESCRIPTION_RU = (
    "📷 Сфоткай чек — распознаю и запишу в проект. К концу — Excel-таблица всех трат."
)

_DESCRIPTION_RU = (
    "Stager — учёт расходов по проектам через Telegram.\n\n"
    "📷 Шлёшь фото чека → распознаю сумму, вендор, дату, категорию → попадает в активный проект.\n"
    "✍️ /add — записать трату текстом.\n"
    "📁 /newproject — несколько проектов параллельно.\n"
    "📋 /list — переключаться между ними.\n"
    "📊 /report — финальная Excel-таблица всех расходов.\n"
    "🔗 /invite — пригласить кого-то в проект."
)


async def _register_commands(bot: Bot) -> None:
    """Команды для выпадайки '/' + описание на карточке бота. Всегда русский —
    мама с en-клиентом видела бы английский и пришлось бы дублировать переводы."""
    # Сносим возможный старый EN-вариант команд
    await bot.delete_my_commands(scope=BotCommandScopeAllPrivateChats(), language_code="en")
    await bot.set_my_commands(_COMMANDS_RU, scope=BotCommandScopeDefault())
    await bot.set_my_commands(_COMMANDS_RU, scope=BotCommandScopeAllPrivateChats())

    # Описание на info-странице бота. Telegram кэширует — обновится не сразу,
    # для пользователя видно при свайпе вверх по аватарке бота или /info.
    try:
        await bot.set_my_short_description(_SHORT_DESCRIPTION_RU)
        await bot.set_my_description(_DESCRIPTION_RU)
    except Exception as exc:  # noqa: BLE001
        # set_my_* возвращает 400 если значение не изменилось — это норм
        log.warning("bot.description_skip", error=str(exc))


async def main() -> None:
    configure_logging()
    init_sentry(service="bot")

    bot_token = os.environ["TELEGRAM_BOT_TOKEN"]
    redis_url = os.environ["REDIS_URL"]

    redis = Redis.from_url(redis_url)
    storage = RedisStorage(redis=redis)
    bot = Bot(token=bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=storage)

    tracing_mw = TracingMiddleware()
    auth_mw = AuthMiddleware(whitelist=_whitelist())
    i18n_mw = I18nMiddleware(default_locale=os.getenv("APP_DEFAULT_LOCALE", "ru"))
    for level in (dp.message, dp.callback_query):
        # порядок важен: tracing → auth → i18n → handler
        level.outer_middleware(tracing_mw)
        level.outer_middleware(auth_mw)
        level.outer_middleware(i18n_mw)

    dp.include_router(start.router)
    dp.include_router(projects.router)
    dp.include_router(expenses.router)
    dp.include_router(report.router)
    dp.include_router(invites.router)
    dp.include_router(photo.router)

    me = await bot.get_me()
    await _register_commands(bot)
    log.info("bot.starting", username=me.username, id=me.id)
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        await redis.aclose()


def run() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    run()
