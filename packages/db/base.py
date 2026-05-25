"""SQLAlchemy 2.0 async setup."""

from __future__ import annotations

import os
import asyncio
import weakref
from asyncio import AbstractEventLoop
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase


DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://stager:stager@postgres:5432/stager")

_engines: weakref.WeakKeyDictionary[AbstractEventLoop, AsyncEngine] = weakref.WeakKeyDictionary()
_sessionmakers: weakref.WeakKeyDictionary[
    AbstractEventLoop,
    async_sessionmaker[AsyncSession],
] = weakref.WeakKeyDictionary()


class Base(DeclarativeBase):
    pass


def get_engine() -> AsyncEngine:
    loop = asyncio.get_running_loop()
    engine = _engines.get(loop)
    if engine is None:
        engine = create_async_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
        _engines[loop] = engine
    return engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    loop = asyncio.get_running_loop()
    sessionmaker = _sessionmakers.get(loop)
    if sessionmaker is None:
        sessionmaker = async_sessionmaker(get_engine(), expire_on_commit=False)
        _sessionmakers[loop] = sessionmaker
    return sessionmaker


async def dispose_engine() -> None:
    loop = asyncio.get_running_loop()
    _sessionmakers.pop(loop, None)
    engine = _engines.pop(loop, None)
    if engine is not None:
        await engine.dispose()


async def get_session() -> AsyncIterator[AsyncSession]:
    async with get_sessionmaker()() as session:
        yield session
