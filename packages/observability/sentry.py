"""Sentry init — один общий enabler для всех трёх процессов.

Использование:
    from packages.observability.sentry import init_sentry
    init_sentry(service="bot")

Если SENTRY_DSN не задан — init_sentry это no-op. Локально и в CI ничего не шлётся.
"""

from __future__ import annotations

import os
from typing import Literal

import sentry_sdk
from sentry_sdk.integrations.asyncio import AsyncioIntegration
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration


Service = Literal["bot", "api", "worker"]


def init_sentry(service: Service) -> None:
    dsn = os.getenv("SENTRY_DSN")
    if not dsn:
        return

    integrations: list = [AsyncioIntegration(), SqlalchemyIntegration()]
    if service == "api":
        integrations += [FastApiIntegration(), StarletteIntegration()]
    if service == "worker":
        integrations += [CeleryIntegration()]

    sentry_sdk.init(
        dsn=dsn,
        integrations=integrations,
        environment=os.getenv("APP_ENV", "dev"),
        release=os.getenv("APP_VERSION", "0.1.0"),
        # 10% traces в проде, 100% в dev — дешёвая телеметрия
        traces_sample_rate=0.1 if os.getenv("APP_ENV") == "prod" else 1.0,
        send_default_pii=False,
        attach_stacktrace=True,
    )
    sentry_sdk.set_tag("service", service)
