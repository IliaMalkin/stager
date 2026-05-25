"""Shared pytest fixtures."""

from __future__ import annotations

import asyncio
import sys
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="session")
def event_loop() -> Iterator[asyncio.AbstractEventLoop]:
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
async def _dispose_db_engine_after_test() -> AsyncIterator[None]:
    # DATABASE_URL for integration tests must point at a test DB
    # (sqlite+aiosqlite or testcontainers/docker Postgres, as configured by the runner).
    yield
    from packages.db.base import dispose_engine

    await dispose_engine()
