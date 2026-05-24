"""Celery app. Imported by `celery -A apps.worker.celery_app`."""

from __future__ import annotations

import os

from celery import Celery
from celery.signals import task_postrun, task_prerun, worker_process_init

from packages.observability import (
    bind_request_id, clear_request_id, configure_logging, init_sentry,
)

configure_logging()


@worker_process_init.connect
def _init_sentry(**_kwargs) -> None:
    init_sentry(service="worker")


@task_prerun.connect
def _bind_trace(task_id: str | None = None, **_kwargs) -> None:
    bind_request_id(task_id[:16] if task_id else None)


@task_postrun.connect
def _clear_trace(**_kwargs) -> None:
    clear_request_id()


celery_app = Celery(
    "stager",
    broker=os.environ["REDIS_URL"],
    backend=os.environ["REDIS_URL"],
    include=["apps.worker.tasks.ocr", "apps.worker.tasks.reports"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=2,
    task_time_limit=120,
    task_soft_time_limit=90,
)
