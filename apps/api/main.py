"""Stager FastAPI app. Run: `uvicorn apps.api.main:app --host 0.0.0.0 --port 8000`."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from apps.api.rate_limit import limiter
from apps.api.routers import auth, expenses, invites, projects, reports
from packages.db.base import dispose_engine, get_engine
from packages.observability import (
    bind_request_id, clear_request_id, configure_logging, init_sentry,
)

log = structlog.get_logger(__name__)


class TracingMiddleware(BaseHTTPMiddleware):
    """Bind request_id from inbound header X-Request-Id (or generate one) and add to response."""

    async def dispatch(self, request: Request, call_next):
        incoming = request.headers.get("x-request-id")
        rid = bind_request_id(incoming)
        try:
            response: Response = await call_next(request)
            response.headers["X-Request-Id"] = rid
            return response
        finally:
            clear_request_id()


def _allowed_origins() -> list[str]:
    raw = os.getenv("CORS_ALLOW_ORIGINS", "")
    if not raw:
        # dev/local — пускаем next dev и localhost
        return ["http://localhost:3000", "http://127.0.0.1:3000"]
    return [o.strip() for o in raw.split(",") if o.strip()]


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    init_sentry(service="api")
    log.info("api.starting")
    yield
    await dispose_engine()
    log.info("api.stopped")


app = FastAPI(
    title="Stager API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/api/v1/docs",
    openapi_url="/api/v1/openapi.json",
)

app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> Response:
    return JSONResponse(
        {"detail": "rate limit exceeded", "limit": str(exc.detail)},
        status_code=429,
    )


# Порядок middleware: outermost первым добавляется
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(TracingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    from redis.asyncio import Redis
    db_ok = False
    redis_ok = False
    try:
        async with get_engine().connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception:  # noqa: BLE001
        pass
    try:
        r = Redis.from_url(os.environ["REDIS_URL"])
        await r.ping()
        await r.aclose()
        redis_ok = True
    except Exception:  # noqa: BLE001
        pass
    status = "ok" if (db_ok and redis_ok) else "degraded"
    return {
        "status": status,
        "db": "ok" if db_ok else "down",
        "redis": "ok" if redis_ok else "down",
    }


for r in (auth.router, projects.router, expenses.router, reports.router, invites.router):
    app.include_router(r, prefix="/api/v1")


def run() -> None:
    import uvicorn
    uvicorn.run("apps.api.main:app", host="0.0.0.0", port=8000)
