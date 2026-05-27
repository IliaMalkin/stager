"""Shared pytest fixtures."""

from __future__ import annotations

import asyncio
import sys
from collections import defaultdict
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import Any

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


class FakeDraftStore:
    def __init__(self) -> None:
        self.values: dict[int, Any] = {}
        self.cleared: list[int] = []
        self.updated: list[tuple[int, dict[str, Any]]] = []

    async def get(self, receipt_id: int) -> Any:
        return self.values.get(receipt_id)

    async def set(self, receipt_id: int, draft: Any) -> None:
        self.values[receipt_id] = draft

    async def update(self, receipt_id: int, **patch: Any) -> Any:
        draft = self.values.get(receipt_id)
        self.updated.append((receipt_id, patch))
        if draft is not None:
            for key, value in patch.items():
                setattr(draft, key, value)
        return draft

    async def clear(self, receipt_id: int) -> None:
        self.cleared.append(receipt_id)
        self.values.pop(receipt_id, None)


class FakeStorage:
    def __init__(self) -> None:
        self.puts: list[tuple[int, bytes, str]] = []

    async def put_receipt(self, project_id: int, data: bytes, filename: str) -> str:
        self.puts.append((project_id, data, filename))
        return f"receipts/{project_id}/{filename}"


class FakeTaskProducer:
    def __init__(self) -> None:
        self.ocr_calls: list[tuple[str, int, int, int, str]] = []

    def enqueue_ocr(
        self,
        file_id: str,
        chat_id: int,
        project_id: int,
        user_tg_id: int,
        locale: str,
    ) -> None:
        self.ocr_calls.append((file_id, chat_id, project_id, user_tg_id, locale))


class FakeSession:
    def __init__(self) -> None:
        self.by_model: defaultdict[type, dict[Any, Any]] = defaultdict(dict)
        self.scalars: dict[type, Any] = {}
        self.execute_rows: list[Any] = []
        self.added: list[Any] = []
        self.deleted: list[Any] = []
        self.flushed = False
        self.committed = False

    async def __aenter__(self) -> "FakeSession":
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        return None

    async def get(self, model: type, key: Any) -> Any:
        return self.by_model[model].get(key)

    async def scalar(self, statement: Any) -> Any:
        column_descriptions = getattr(statement, "column_descriptions", [])
        if column_descriptions:
            model = column_descriptions[0].get("entity")
            if model in self.scalars:
                return self.scalars[model]
        return None

    async def execute(self, statement: Any) -> "FakeResult":
        return FakeResult(self.execute_rows)

    def add(self, value: Any) -> None:
        self.added.append(value)

    async def delete(self, value: Any) -> None:
        self.deleted.append(value)
        for values in self.by_model.values():
            for key, stored in list(values.items()):
                if stored is value:
                    values.pop(key)

    async def flush(self) -> None:
        self.flushed = True
        for index, value in enumerate(self.added, start=1):
            if getattr(value, "id", None) is None:
                value.id = index

    async def commit(self) -> None:
        self.committed = True


class FakeScalarResult:
    def __init__(self, rows: list[Any]) -> None:
        self.rows = rows

    def all(self) -> list[Any]:
        return self.rows


class FakeResult:
    def __init__(self, rows: list[Any]) -> None:
        self.rows = rows

    def scalars(self) -> FakeScalarResult:
        return FakeScalarResult(self.rows)


@pytest.fixture
def fake_session_factory() -> tuple[Any, FakeSession]:
    session = FakeSession()

    def factory() -> FakeSession:
        return session

    return factory, session


@pytest.fixture
def fake_drafts() -> FakeDraftStore:
    return FakeDraftStore()


@pytest.fixture
def fake_storage() -> FakeStorage:
    return FakeStorage()


@pytest.fixture
def fake_producer() -> FakeTaskProducer:
    return FakeTaskProducer()
