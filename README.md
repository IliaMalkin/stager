# Stager

> Multi-tenant project expense tracker for home-staging businesses. Snap a receipt in Telegram, get a finished spreadsheet at the end of the project.

[![CI](https://github.com/kudnever/stager/actions/workflows/ci.yml/badge.svg)](https://github.com/kudnever/stager/actions/workflows/ci.yml)
![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)
![Next.js 14](https://img.shields.io/badge/next.js-14-black.svg)
![License MIT](https://img.shields.io/badge/license-MIT-green.svg)

## Why this exists

My mom runs a home-staging business in Russia. She prepares apartments for sale — rents furniture, hires crews, organizes deliveries. She runs 2–3 projects in parallel and tracks expenses by writing them into the chat with each client. Compiling the final expense table at the end of a project takes hours.

**Stager replaces that with a Telegram bot.** She snaps a photo of a receipt → an LLM extracts the amount, vendor, date and category → it lands in the active project. `/report` produces an XLSX.

The same bot is multi-tenant from day one, so I use it for my own expense tracking too.

## Architecture

```
Telegram ─► aiogram bot ──► Postgres
                       └─► Redis ──► Celery worker ──► MinIO (receipt photos)
                                                  └─► LLM router (MiMo → Gemini fallback)
                       └─► FastAPI ◄── Next.js admin (recharts, JWT in httpOnly cookie)
```

Single Docker Compose stack. Caddy in front, Sentry + structlog for observability.

See [ARCHITECTURE.md](ARCHITECTURE.md) for the design rationale, [ROADMAP.md](ROADMAP.md) for the build plan.

## LLM router — the interesting bit

[`packages/llm/router.py`](packages/llm/router.py) is a unified `chat()` / `vision()` interface that tries **MiMo (Xiaomi)** first and falls back to **Google Gemini** on rate-limits, auth failures, timeouts, or schema-validation errors. A Redis-backed soft circuit breaker disables MiMo for an hour after repeated 401/403 events.

```python
from packages.llm import build_router, OCRResult, RECEIPT_OCR_PROMPT

router = build_router()
result, meta = await router.vision(
    image_bytes=jpg,
    prompt=RECEIPT_OCR_PROMPT,
    response_format=OCRResult,
    request_id="receipt:42",
)
# meta.provider == "mimo" | "gemini"
# meta.fallback_reason ∈ {None, "rate_limited", "timeout", "validation_error", ...}
```

Every call is logged with `request_id`, provider, latency, tokens, and fallback reason. Trivial to wire to Grafana later.

## Tech choices

| Layer | Tool | Why |
|---|---|---|
| Bot | aiogram 3 + FSM via Redis | Native async, modern API |
| API | FastAPI + Pydantic v2 | Async, OpenAPI for free |
| DB | PostgreSQL 16 + SQLAlchemy 2.0 (async) | JSONB for raw OCR audit |
| Queue | Celery + Redis | Standard, well-known |
| Storage | MinIO (S3-compatible) | Self-hosted, S3-portable |
| Frontend | Next.js 14 App Router + Tailwind | SSR-first, JWT never leaves the server |
| LLM | MiMo (Xiaomi) → Gemini fallback | See router section |
| Reports | openpyxl | Multi-sheet XLSX for mom |
| Observability | structlog + Sentry | Request-id propagation across all 3 services |
| Tests | pytest + testcontainers + respx | Real Postgres in CI, no sqlite shortcut |
| Deploy | Docker Compose + Caddy on Hetzner | One server, one box, no Kubernetes |

## Quickstart (development)

```bash
git clone https://github.com/kudnever/stager.git
cd stager
cp .env.example .env
# Fill in TELEGRAM_BOT_TOKEN, MIMO_API_KEY, GOOGLE_API_KEY, JWT_SECRET

make up         # boots postgres + redis + minio + bot + api + worker
make migrate    # apply schema
make create-admin   # interactive: web admin login
make seed       # optional: dev fixtures
make test       # pytest with real Postgres + Redis
```

Web admin: `http://localhost:3000`
API docs: `http://localhost:8000/api/v1/docs`

## Production deploy

See [deploy/README.md](deploy/README.md).

## Status

MVP shipped. See [ROADMAP.md](ROADMAP.md) for what's next (rental return reminders, PDF client report, voice replies via MiMo TTS).

## License

MIT. Built solo as a real-world project that also serves as a CV piece. Source layout, observability story, and provider-fallback router are intentionally over-explained for that reason — see [ARCHITECTURE.md](ARCHITECTURE.md) for design notes a reviewer would want to read.
