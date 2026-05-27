from __future__ import annotations

import pytest


def test_process_receipt_notifies_user_after_retryable_failures_are_exhausted(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/15")
    from apps.worker.tasks import ocr

    async def fail_task(*_args, **_kwargs):
        raise OSError("telegram download failed")

    notifications: list[tuple[int, str]] = []

    monkeypatch.setattr(ocr, "_run_task", fail_task)
    monkeypatch.setattr(
        ocr,
        "_notify_failed_sync",
        lambda chat_id, locale: notifications.append((chat_id, locale)),
    )

    ocr.process_receipt.push_request(retries=ocr.process_receipt.max_retries)
    try:
        result = ocr.process_receipt.run("file-id", 123, 456, 20, "ru")
    finally:
        ocr.process_receipt.pop_request()

    assert result == {"status": "failed", "error": "telegram download failed"}
    assert notifications == [(456, "ru")]


def test_process_receipt_retries_retryable_failures_before_final_notification(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/15")
    from apps.worker.tasks import ocr

    class RetryRaised(Exception):
        pass

    async def fail_task(*_args, **_kwargs):
        raise OSError("temporary telegram error")

    def retry(*, exc):
        raise RetryRaised(str(exc))

    notifications: list[tuple[int, str]] = []

    monkeypatch.setattr(ocr, "_run_task", fail_task)
    monkeypatch.setattr(ocr.process_receipt, "retry", retry)
    monkeypatch.setattr(
        ocr,
        "_notify_failed_sync",
        lambda chat_id, locale: notifications.append((chat_id, locale)),
    )

    ocr.process_receipt.push_request(retries=0)
    try:
        with pytest.raises(RetryRaised, match="temporary telegram error"):
            ocr.process_receipt.run("file-id", 123, 456, 20, "ru")
    finally:
        ocr.process_receipt.pop_request()

    assert notifications == []
