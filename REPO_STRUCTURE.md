# Repo structure

```
stager/
├── ARCHITECTURE.md              # эта спека
├── ROADMAP.md                   # 2-week plan
├── REPO_STRUCTURE.md            # этот файл
├── README.md                    # public overview, EN
├── README-user.ru.md            # end-user instruction, RU
├── LICENSE                      # MIT
├── Makefile                     # up/down/logs/test/migrate/lint
├── docker-compose.yml           # dev stack
├── docker-compose.prod.yml      # prod overrides (но secrets — в private repo)
├── .env.example
├── .gitignore
├── .dockerignore
├── pyproject.toml               # один проект для bot+api+worker (shared deps)
├── alembic.ini
├── .github/
│   └── workflows/
│       ├── ci.yml               # lint + test + build
│       └── docker-build.yml     # на push в main, билд образов
│
├── apps/
│   ├── bot/                     # Telegram бот
│   │   ├── Dockerfile
│   │   ├── main.py              # entry: aiogram dispatcher
│   │   ├── handlers/
│   │   │   ├── start.py
│   │   │   ├── projects.py     # /newproject /list /switch
│   │   │   ├── expenses.py    # /add
│   │   │   ├── photo.py        # photo flow + FSM
│   │   │   ├── report.py
│   │   │   └── invites.py
│   │   ├── fsm/
│   │   │   ├── new_project.py
│   │   │   └── photo_review.py
│   │   ├── keyboards.py
│   │   ├── middlewares.py       # auth, i18n, logging
│   │   └── i18n/
│   │       ├── ru.json
│   │       └── en.json
│   │
│   ├── api/                     # FastAPI
│   │   ├── Dockerfile
│   │   ├── main.py              # FastAPI app factory
│   │   ├── routers/
│   │   │   ├── auth.py
│   │   │   ├── projects.py
│   │   │   ├── expenses.py
│   │   │   ├── reports.py
│   │   │   └── invites.py
│   │   ├── deps.py              # JWT auth dependency, db session
│   │   ├── schemas/             # Pydantic request/response
│   │   └── cli.py               # `stager create-admin` etc.
│   │
│   ├── worker/                  # Celery
│   │   ├── Dockerfile
│   │   ├── celery_app.py
│   │   ├── tasks/
│   │   │   ├── ocr.py           # фото → llm.vision → expense draft
│   │   │   ├── reports.py       # XLSX/CSV generation
│   │   │   └── notifications.py # extension: rental return reminders
│   │   └── beat_schedule.py     # пустой пока, extension fills
│   │
│   └── web/                     # Next.js 14
│       ├── Dockerfile
│       ├── package.json
│       ├── next.config.js
│       ├── tailwind.config.ts
│       ├── app/
│       │   ├── layout.tsx
│       │   ├── (auth)/login/page.tsx
│       │   └── (app)/
│       │       ├── projects/page.tsx
│       │       ├── projects/[id]/page.tsx
│       │       └── settings/page.tsx
│       ├── components/
│       │   ├── ui/              # shadcn auto-generated
│       │   ├── ExpensesTable.tsx
│       │   ├── CategoryPie.tsx
│       │   └── DailyLine.tsx
│       └── lib/
│           ├── api.ts           # fetch helper
│           └── auth.ts
│
├── packages/                    # переиспользуемое между apps/
│   ├── db/                      # SQLAlchemy модели и сессии
│   │   ├── __init__.py
│   │   ├── base.py              # declarative base, async engine
│   │   ├── models.py            # все модели одним файлом (MVP)
│   │   └── session.py
│   │
│   ├── domain/                  # чистая бизнес-логика, без I/O
│   │   ├── __init__.py
│   │   ├── categories.py        # enum + i18n labels
│   │   ├── parsers.py           # /add парсер
│   │   ├── currency.py          # форматирование, minor units
│   │   └── reports.py           # агрегации (in-memory)
│   │
│   ├── llm/                     # 🌟 главный artifact
│   │   ├── __init__.py
│   │   ├── router.py            # MiMo → Gemini fallback
│   │   ├── providers/
│   │   │   ├── mimo.py
│   │   │   └── gemini.py
│   │   ├── prompts/
│   │   │   └── receipt_ocr.py   # промпт + Pydantic OCRResult
│   │   ├── metrics.py           # counters, logged for now
│   │   └── circuit_breaker.py   # Redis-based, MiMo soft-disable
│   │
│   ├── storage/                 # MinIO/S3 wrapper
│   │   ├── __init__.py
│   │   └── minio_client.py
│   │
│   └── observability/
│       ├── __init__.py
│       ├── logging.py           # structlog setup
│       └── sentry.py
│
├── migrations/                  # Alembic
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 0001_initial.py      # все MVP таблицы
│
├── tests/
│   ├── conftest.py              # testcontainers fixtures
│   ├── unit/
│   │   ├── domain/
│   │   └── llm/
│   ├── integration/
│   │   ├── test_models.py
│   │   ├── test_api.py
│   │   └── test_bot_handlers.py
│   └── e2e/
│       └── test_photo_flow.py
│
└── scripts/
    ├── seed_dev.py              # тестовые проекты + расходы для dev
    └── backup.sh                # pg_dump → /var/backups
```

**Принципы:**
- `apps/*` — точки входа, тонкие. Бизнес-логика в `packages/`.
- `packages/db` импортируется всеми `apps/*` напрямую.
- `packages/domain` — pure Python, без I/O, легко юнит-тестируется.
- `packages/llm` — единственное место где живут httpx-клиенты MiMo/Gemini.
- Все Python в одном `pyproject.toml` (monorepo light), один venv.
