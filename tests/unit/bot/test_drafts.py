"""Тесты ReceiptDraftStore — Redis обёрнут fakeredis или мокаем напрямую."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from apps.bot.drafts import Draft, ReceiptDraftStore


@pytest.fixture
def redis_mock():
    storage: dict[str, str] = {}

    m = AsyncMock()

    async def _set(key, value, ex=None):
        storage[key] = value
        return True

    async def _get(key):
        return storage.get(key)

    async def _delete(key):
        storage.pop(key, None)
        return 1

    m.set.side_effect = _set
    m.get.side_effect = _get
    m.delete.side_effect = _delete
    return m


async def test_set_and_get(redis_mock):
    store = ReceiptDraftStore(redis_mock)
    d = Draft(amount=485.50, vendor="IKEA", category="furniture", confidence=0.92)
    await store.set(42, d)
    got = await store.get(42)
    assert got is not None
    assert got.amount == 485.50
    assert got.vendor == "IKEA"
    assert got.category == "furniture"


async def test_get_missing(redis_mock):
    store = ReceiptDraftStore(redis_mock)
    assert await store.get(999) is None


async def test_update_patches_fields(redis_mock):
    store = ReceiptDraftStore(redis_mock)
    await store.set(7, Draft(amount=100.0, vendor="X", category="other"))
    updated = await store.update(7, vendor="Y", category="furniture")
    assert updated is not None
    assert updated.vendor == "Y"
    assert updated.category == "furniture"
    assert updated.amount == 100.0  # not touched


async def test_update_missing_returns_none(redis_mock):
    store = ReceiptDraftStore(redis_mock)
    assert await store.update(999, vendor="Z") is None


async def test_clear(redis_mock):
    store = ReceiptDraftStore(redis_mock)
    await store.set(5, Draft(amount=10.0))
    await store.clear(5)
    assert await store.get(5) is None


def test_is_ready_to_save():
    assert Draft(amount=100.0).is_ready_to_save() is True
    assert Draft(amount=None).is_ready_to_save() is False
    assert Draft().is_ready_to_save() is False
