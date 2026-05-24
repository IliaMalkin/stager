# MVP Roadmap — 2 недели

Цель: к концу Week 2 мама шлёт первый чек в прод-бота на `stager.kudnever.dev`.

Дни разбиты так, что **независимые задачи помечены `[||]`** — их можно параллелить через Claude Code subagents.

---

## Week 1 — backbone

### Day 1 (Пн) — scaffolding

- [ ] `git init`, push в `github.com/kudnever/stager` (public, MIT)
- [ ] Структура репо (см. §16 ARCHITECTURE.md)
- [ ] `pyproject.toml` + `requirements.txt` (или uv lock)
- [ ] `docker-compose.yml` с postgres/redis/minio (только инфра)
- [ ] `.env.example`, `.gitignore`
- [ ] `make up` / `make down` / `make logs` / `make test` / `make migrate`
- **Done when:** `make up` поднимает 3 stateful сервиса, все healthy

### Day 2 (Вт) — БД и миграции `[||]`

- [ ] SQLAlchemy 2.0 async setup (`packages/db/`)
- [ ] Все модели из §5 ARCHITECTURE.md (один файл `models.py` пока)
- [ ] Alembic init + первая миграция (все таблицы одним коммитом)
- [ ] Pytest fixture: testcontainers postgres
- [ ] Тест: upgrade head → 5 таблиц существуют, FK живые

### Day 3 (Ср) — LLM router `[||]`

- [ ] `packages/llm/router.py` — реализация по §8 ARCHITECTURE.md
- [ ] Pydantic `OCRResult` модель
- [ ] MiMo client (httpx, OpenAI-compatible)
- [ ] Gemini client (google-genai SDK)
- [ ] Структурный лог через structlog
- [ ] Redis-based soft circuit breaker
- [ ] Тесты: respx-моки на MiMo 429/401/timeout → проверяем fallback на Gemini
- **Done when:** `pytest packages/llm/` зелёный, в т.ч. fallback-сценарии

### Day 4 (Чт) — bot skeleton

- [ ] `apps/bot/main.py` — aiogram3 dispatcher, RedisStorage
- [ ] `/start [<token>]` handler с invite-redeem + whitelist
- [ ] `/help`, `/cancel`
- [ ] `/newproject` FSM (name → budget → confirm)
- [ ] `/list`, `/switch` (без inline-кнопок пока, просто текст)
- [ ] i18n каркас (RU/EN), aiogram middleware
- **Done when:** локально в Telegram создаётся проект, делается активным

### Day 5 (Пт) — bot photo flow (без OCR) `[||]`

- [ ] Photo handler: сохраняем в MinIO, создаём `Receipt(ocr_status=pending)`
- [ ] Celery task `ocr_task` (stub: возвращает фиктивный JSON через 2 сек)
- [ ] FSM review card с inline-кнопками
- [ ] Edit handlers: amount / category / vendor
- [ ] Save → создаёт expense
- **Done when:** фото → карточка → Сохранить → запись в expenses

---

## Week 2 — completeness

### Day 6 (Пн) — реальный OCR

- [ ] `ocr_task` теперь вызывает `llm.vision(image_bytes, prompt, response_format=OCRResult)`
- [ ] mapping `OCRResult` → review-card text
- [ ] Confidence < 0.6 или amount=null → `needs_review` + disabled Save
- [ ] retry-policy: ocr_attempts max 3
- **Done when:** реальный чек → реальная карточка с реальной суммой

### Day 7 (Вт) — /add и /report `[||]`

- [ ] `/add` парсер
- [ ] `/report` команда: текстовая сводка (total, by category, count)
- [ ] `/report` кнопка `📥 Скачать` → Celery task генерит XLSX через openpyxl
- [ ] Бот отправляет файл в чат

### Day 8 (Ср) — FastAPI auth + projects `[||]`

- [ ] `apps/api/main.py` — FastAPI + JWT middleware
- [ ] `/auth/login`, `/auth/me`
- [ ] `/projects` CRUD
- [ ] `/projects/{id}/expenses` GET (с фильтрами from/to/category)
- [ ] Health check
- [ ] CLI команда `stager create-admin <email> <password>`
- [ ] Тесты на RBAC: нельзя чужой проект

### Day 9 (Чт) — FastAPI reports + invites `[||]`

- [ ] `/reports/summary` (total + by_category + by_day)
- [ ] `/reports/export.csv` + `.xlsx`
- [ ] `/invites` POST + redeem-логика в bot
- [ ] `/expenses/{id}` PATCH/DELETE

### Day 10 (Пт) — Next.js admin ✅

- [x] `apps/web` — Next.js 14 App Router, Tailwind, ручные shadcn-style компоненты
- [x] Login page + server action, JWT в httpOnly cookie + middleware-redirect
- [x] /projects list (cards) + /projects/[id] (detail)
- [x] Expenses table с фильтрами from/to/category/source через query params
- [x] CategoryPie + DailyLine (recharts, client components)
- [x] Кнопки Download CSV / XLSX через /projects/[id]/download proxy-route

### Day 11 (Сб) — CI/CD + observability ✅

- [x] GitHub Actions: ruff + mypy (strict на packages+api) + pytest с реальными Postgres+Redis + coverage artifact
- [x] Sentry SDK integration (bot, api, worker) — через [`packages/observability/sentry.py`](packages/observability/sentry.py)
- [x] structlog с trace_id во всех 3-х процессах — через TracingMiddleware (bot + API) + Celery signals
- [x] X-Request-Id propagation в HTTP response
- [x] Fixes из code review: AuthMiddleware на правильном уровне, ON DELETE CASCADE, Celery task_time_limit, slowapi на /auth/login, единый pyproject как source of truth
- [x] H2: Receipt drafts → Redis (`apps/bot/drafts.py`), raw_ocr_text стал иммутабельным audit-полем
- [x] H3: module-level cache для Bot/Router/Storage в worker
- [x] H5: узкое ретраение (_RETRYABLE = httpx/Mimo/Gemini Errors), программные баги fail loud
- [x] Health-check на api теперь проверяет и DB и Redis
- [x] Pre-commit hooks (ruff + gitleaks + no-commit-to-main) — [`.pre-commit-config.yaml`](.pre-commit-config.yaml)
- [x] Тесты bot-слоя: drafts store, i18n loader, keyboards, invite redeem flow (integration)

### Day 12 (Вс) — prod deploy на Hetzner [твои руки]

- [x] `docker-compose.prod.yml` — overlay с restart=always + закрытыми портами
- [x] `deploy/Caddyfile` для stager.kudnever.dev
- [x] `deploy/backup.sh` — pg_dump cron + MinIO mirror
- [x] `deploy/README.md` — пошаговый runbook
- [ ] DNS A-запись `stager.kudnever.dev` → 178.105.163.2 [ручное]
- [ ] `.env.production` залить на сервер [ручное]
- [ ] `docker compose ... up -d` [ручное]

### Day 13 (Пн) — UAT с мамой ✅ (готов сценарий)

- [x] [`UAT.md`](UAT.md) — пошаговый скрипт прогона на 20 минут
- [ ] Реальный прогон [ручное]
- [ ] Сбор жалоб → `UAT_FEEDBACK.md`

### Day 14 (Вт) — стабилизация + CV-полировка ✅ (частично)

- [x] README.md обновлён под CV-аудиторию: badges, tech-stack table, LLM router как hero-feature
- [x] [`scripts/probe_mimo.py`](scripts/probe_mimo.py) — sanity check MiMo vision API до Day 5
- [ ] Демо-гифка [ручное, после UAT]
- [ ] git tag `v0.1.0` + GitHub release [ручное]
- [ ] LinkedIn / hh.ru пост [ручное]

---

## Параллелизация через subagents

В дни помеченные `[||]` — независимая работа. Команды для Claude Code:

- **Day 2 + Day 3 одновременно:** один subagent делает БД-слой (модели + миграции + тесты), второй — llm/router (independent — нет общих файлов)
- **Day 8 + Day 9:** один subagent API auth+projects, другой — invites endpoint (после того как Day 8 закончен по API skeleton)
- **Day 11:** CI workflow и Sentry integration независимы

Не параллелить: Day 4 → 5 → 6 (зависимость bot → photo → OCR), Day 10 (web ждёт API).
