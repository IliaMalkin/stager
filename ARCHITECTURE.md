# Stager — Architecture & MVP Spec

> Telegram-бот + web-админка для учёта расходов по проектам. Главный пользователь — мама-home-stager. MVP за 2 недели. Junior-grade монолит.

---

## 1. Stakeholders & goals

| # | Stakeholder | Главное что должно работать |
|---|---|---|
| A | Мама (home-stager в РФ) | Фоткает чек в чате с ботом → к концу проекта получает CSV/Excel со всеми тратами по категориям |
| B | Илья (личный учёт) | Тот же flow для других доменов (мульти-тенант с дня 1) |
| C | CV / job market | Покрывать ≥50% требований из 11 отслеживаемых junior-вакансий за 1 месяц |

**Одна фраза для мамы:** «К концу проекта итоговая таблица всех трат строится сама — больше не собираешь по чатам».

---

## 2. Personas

**Мама.** Ведёт 2-3 проекта параллельно. Сейчас пишет траты в чат с заказчиком. Чеки фоткает «для подстраховки». В магазине, на стройке, в машине — мобильный сценарий. Не любит формы, любит сообщения.

**Илья.** Personal finance через тот же бот. Привык к CLI и pet-проектам. Будет также админом web-интерфейса.

---

## 3. MVP user stories (с acceptance criteria)

### US-1. Регистрация по invite

- Мама получает от Ильи ссылку `t.me/stager_bot?start=<invite_token>`
- `/start <token>` → запись в `users`, `project_members` (если токен привязан к проекту), приветственное сообщение по-русски
- **AC:** без валидного токена и не в whitelist → бот отвечает «бот закрытый, нужен инвайт» и ничего не пишет в БД

### US-2. Создание проекта

- `/newproject` → FSM-визард: «Как назовём проект?» → «Бюджет (опционально, можно пропустить)?» → «Валюта по умолчанию RUB, [Изменить]/[OK]»
- **AC:** проект создан, текущий user становится owner, проект автоматически делается активным в `active_context`

### US-3. Активный проект и переключение

- `/list` → список моих проектов с балансом, inline-кнопками `Switch` на каждом
- `/switch` → inline-кнопки выбора
- **AC:** все последующие /add и фото идут в активный проект; при переключении бот подтверждает «активный проект → X»

### US-4. Текстовая запись расхода

- `/add 4850 мебель диван из ИКЕА`
- Парсер: первое число = сумма, опциональная категория из enum, остальное — описание
- **AC:** при невалидном формате — подсказка с примером

### US-5. Фото чека (главный flow)

1. Мама шлёт фото
2. Бот мгновенно: «📷 принял, секунду…»
3. Celery: фото → MinIO → llm.vision (MiMo → fallback Gemini) → JSON
4. Бот шлёт карточку:
   ```
   🧾 ИКЕА Парнас
   💰 4 850 ₽
   📅 2026-05-23
   🏷  мебель
   [✅ Сохранить] [✏️ Сумма] [✏️ Категория] [✏️ Вендор] [❌ Отмена]
   ```
5. На `Сохранить` — пишется `expense + receipt`
6. На `Поправить *` — FSM-стейт edit_amount / edit_category / edit_vendor
- **AC:** при `confidence < 0.6` или `amount=null` — карточка помечается ⚠️ и кнопка `Сохранить` неактивна до правки

### US-6. Финальный отчёт

- `/report` → краткая сводка текущего проекта: total, breakdown по категориям, число чеков
- Кнопка `📥 Скачать таблицу` → бот шлёт `<project_name>_report.xlsx` (sheet: расходы / категории / сводка)
- **AC:** даты и категории корректны, total бьётся со sum(amount_minor)/100

### US-7. Web admin (минимум)

- Login по JWT (логин = email + пароль, выпускается через CLI команду)
- Страницы: проекты (list/detail), расходы (table с фильтрами), 2 чарта (pie/line), кнопка `Download CSV`
- **AC:** изменения сделанные в боте видны в web в течение 5 сек (без явного refresh — OK)

---

## 4. Архитектурная диаграмма

```
                    ┌──────────────────────────────┐
                    │   Telegram (внешний канал)   │
                    └──────────────┬───────────────┘
                                   │ long-polling (aiogram)
              ┌────────────────────▼─────────────────────┐
              │            stager-bot (Python)           │
              │  aiogram3 dispatcher + FSM + handlers    │
              └──┬────────────────────────────────────┬──┘
                 │ enqueue                            │ select/insert
                 │                                    │
       ┌─────────▼────────┐                    ┌──────▼──────────┐
       │  Redis (broker)  │                    │  PostgreSQL 16  │
       └─────────┬────────┘                    └──────┬──────────┘
                 │ task                                ▲
       ┌─────────▼─────────────┐                       │
       │ stager-worker (Celery)│                       │
       │  - ocr_task           │ ──── llm.vision ──┐   │
       │  - report_export_task │                   │   │
       └─────────┬─────────────┘                   │   │
                 │ put                             │   │
       ┌─────────▼────────┐              ┌─────────▼───┴───┐
       │  MinIO (S3)      │              │  llm/router.py  │
       │  receipts/<uuid> │              │  MiMo → Gemini  │
       └──────────────────┘              └─────────────────┘
                                                 ▲
              ┌──────────────────────────────────┘
              │
       ┌──────┴──────────┐    HTTPS    ┌─────────────────────────┐
       │   stager-api    │◄────────────┤  stager-web (Next.js)   │
       │   FastAPI+JWT   │             │  admin UI               │
       └─────────────────┘             └─────────────────────────┘
                ▲                                ▲
                └─────────── Caddy (TLS) ────────┘
                       stager.kudnever.dev
```

**Все 5 контейнеров** (bot, api, worker, web, caddy) + 3 stateful (postgres, redis, minio) живут в одном Compose-стеке на Hetzner-178.105.163.2 рядом с hermes.

---

## 5. Database schema

> SQLAlchemy 2.0 declarative, async session. Все денежные значения — `BigInteger` в минорных единицах (копейки). Все timestamps — `timezone=True`.

```python
class User(Base):
    __tablename__ = "users"
    id: int  # PK
    telegram_id: int  # UNIQUE, indexed
    username: str | None
    full_name: str | None
    locale: str = "ru"  # "ru"|"en"
    email: str | None  # для web-admin login
    password_hash: str | None  # bcrypt
    role: Literal["admin", "user"] = "user"  # глобальная роль (admin = Илья)
    created_at: datetime

class Project(Base):
    __tablename__ = "projects"
    id: int  # PK
    owner_user_id: int  # FK users.id, indexed
    name: str
    currency: str = "RUB"  # ISO 4217, immutable после создания
    budget_minor: int | None
    status: Literal["active", "completed", "archived"] = "active"
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None

class ProjectMember(Base):
    __tablename__ = "project_members"
    # composite PK (user_id, project_id)
    user_id: int  # FK users.id
    project_id: int  # FK projects.id
    role: Literal["owner", "editor", "viewer"] = "editor"
    created_at: datetime

class ActiveContext(Base):
    __tablename__ = "active_context"
    user_id: int  # PK, FK users.id
    current_project_id: int | None  # FK projects.id
    updated_at: datetime

class Expense(Base):
    __tablename__ = "expenses"
    id: int  # PK
    project_id: int  # FK projects.id, indexed
    amount_minor: int  # сумма в копейках
    currency: str  # денормализуется из projects.currency на момент создания
    category: str  # enum (см. §6)
    description: str | None
    paid_at: date  # дата покупки (не created_at)
    created_by_user_id: int  # FK users.id
    source: Literal["bot_photo", "bot_text", "admin_web"]
    receipt_id: int | None  # FK receipts.id
    raw_ocr_json: dict | None  # JSONB, для аудита
    created_at: datetime
    # indexes: (project_id, paid_at), (project_id, category)

class Receipt(Base):
    __tablename__ = "receipts"
    id: int  # PK
    expense_id: int | None  # FK expenses.id (nullable: фото может прийти до подтверждения)
    minio_key: str  # путь в bucket: receipts/{project_id}/{uuid}.jpg
    original_filename: str | None
    ocr_status: Literal["pending", "ok", "failed", "needs_review"]
    ocr_attempts: int = 0
    ocr_provider: str | None  # "mimo:mimo-v2-omni" | "gemini:gemini-2.5-flash"
    raw_ocr_text: str | None
    created_at: datetime

class Invite(Base):
    __tablename__ = "invites"
    id: int  # PK
    token: str  # UNIQUE, indexed, 32-char urlsafe
    issued_by_user_id: int  # FK users.id
    project_id: int | None  # FK projects.id (опционально привязать к проекту)
    role: Literal["editor", "viewer"] = "editor"
    expires_at: datetime
    used_by_user_id: int | None  # FK users.id, NULL до redeem
    used_at: datetime | None
    created_at: datetime
```

**Alembic первая миграция** — все эти таблицы одним коммитом. Никаких миграций «по одной таблице».

---

## 6. Категории (fixed enum)

`stager.domain.categories.Category` (Python StrEnum + БД-constraint):

| key | RU | EN |
|---|---|---|
| `furniture` | мебель | furniture |
| `decor` | декор | decor |
| `textile` | текстиль | textile |
| `delivery` | доставка | delivery |
| `labor` | бригада | labor |
| `supplies` | расходники | supplies |
| `photo` | фото | photo |
| `rental` | аренда | rental |
| `transport` | транспорт | transport |
| `other` | прочее | other |

LLM получает этот список в промпте и обязан вернуть один ключ.

---

## 7. Bot commands & FSM

```
/start [<token>]    публичная команда, redeem инвайт-токена
/help               список команд
/newproject         FSM: name → budget? → currency? → confirm
/list               проекты + inline switch
/switch             inline-выбор активного
/add <amount> [cat] [desc]   быстрая текстовая запись
/report             сводка активного + кнопка скачать xlsx
/invite             [owner only] выдать инвайт-ссылку
/cancel             выйти из любого FSM-стейта
```

**Photo flow FSM (aiogram FSMContext):**

```
[idle]
   │ photo received
   ▼
[ocr_running]    ─── timeout 30s ───► [ocr_failed] (можно повторить)
   │ ok                                    │
   ▼                                       │
[review_card]   user taps:                 │
   ├── [Сохранить] ───► insert expense, [idle], confirm
   ├── [Сумма]     ───► [edit_amount]   ─► back to [review_card]
   ├── [Категория] ───► [edit_category] ─► back to [review_card]
   ├── [Вендор]    ───► [edit_vendor]   ─► back to [review_card]
   └── [Отмена]    ───► delete receipt, [idle]
```

FSM-state хранится в Redis (aiogram default storage = RedisStorage2).

---

## 8. LLM router design

**Контракт:**

```python
class LLMRouter:
    async def chat(
        self,
        messages: list[dict],
        *,
        response_format: type[BaseModel] | None = None,
        complexity: Literal["fast", "smart"] = "fast",
        request_id: str,
    ) -> tuple[BaseModel | str, LLMCallMeta]: ...

    async def vision(
        self,
        image_bytes: bytes,
        prompt: str,
        *,
        response_format: type[BaseModel],
        request_id: str,
    ) -> tuple[BaseModel, LLMCallMeta]: ...
```

`LLMCallMeta` = `{provider, model, tokens_in, tokens_out, latency_ms, fallback_reason: str | None, attempts: int}`.

**Try-order:**

| complexity | primary | fallback |
|---|---|---|
| `vision` | mimo-v2-omni | gemini-2.5-flash |
| `fast` | mimo-v2.5 | gemini-2.5-flash |
| `smart` | mimo-v2.5-pro | gemini-2.5-pro |

**Fallback triggers:**
- HTTP 401/403 (signals MiMo revoke — log WARNING)
- HTTP 429 (rate-limited)
- HTTP 5xx
- Timeout > 30s (vision) / > 15s (chat)
- `response_format` valid и Pydantic-парсинг упал
- Exception в SDK-вызове

**После 3-х подряд fallback по 401/403** — `MIMO_DISABLED_UNTIL` поднимается в Redis на 1 час (мягкий circuit-breaker), все запросы идут сразу на Gemini.

**Метрики (Prometheus-style counters в structlog, потом легко scrape):**
- `llm_calls_total{provider, model, result=success|fallback|error}`
- `llm_latency_seconds{provider, model}` (histogram)
- `llm_tokens_total{provider, model, direction=in|out}`

**Все вызовы логируются** structured-логом с полями `request_id, provider, model, fallback_reason, tokens, latency_ms`. `request_id` пробрасывается из `expenses.id`-будущего / `receipts.id` для корреляции.

---

## 9. OCR prompt (единый для MiMo и Gemini)

```text
System:
Ты помощник для обработки чеков. Тебе дано фото чека.
Извлеки данные. Ответь СТРОГО валидным JSON без markdown, без комментариев.

Схема:
{
  "amount": number,        // итоговая сумма, в денежных единицах (4850.50)
  "currency": "RUB" | "USD" | "EUR",
  "vendor": string,        // название магазина/поставщика
  "date": "YYYY-MM-DD" | null,
  "category_guess": "furniture" | "decor" | "textile" | "delivery" | "labor"
                  | "supplies" | "photo" | "rental" | "transport" | "other",
  "items": [{"name": string, "qty": number, "price": number}],  // optional, можно []
  "confidence": number     // 0.0 - 1.0, оценка достоверности
}

Правила:
- Сумма = ИТОГО / TOTAL / К ОПЛАТЕ. Не подитог.
- Если не видно даты — date = null.
- Если фото нечитаемое — confidence < 0.3, остальные поля best effort.
- Categori­ze по совокупности: вендор + items.
```

Структура валидируется на стороне роутера через Pydantic `OCRResult`. При parse error → fallback.

---

## 10. FastAPI REST contract

Все эндпоинты `/api/v1/*`. JWT в `Authorization: Bearer <token>`.

| Method | Path | Body | Response |
|---|---|---|---|
| POST | `/auth/login` | `{email, password}` | `{access_token, expires_at}` |
| GET | `/auth/me` | — | `User` |
| GET | `/projects` | — | `[Project]` (только мои) |
| POST | `/projects` | `{name, currency?, budget_minor?}` | `Project` |
| GET | `/projects/{id}` | — | `Project` (+ members) |
| PATCH | `/projects/{id}` | partial | `Project` |
| DELETE | `/projects/{id}` | — | `204` |
| GET | `/projects/{id}/expenses` | query: `from, to, category, source` | `[Expense]` |
| POST | `/projects/{id}/expenses` | `{amount_minor, category, description?, paid_at}` | `Expense` |
| PATCH | `/expenses/{id}` | partial | `Expense` |
| DELETE | `/expenses/{id}` | — | `204` |
| GET | `/projects/{id}/report/summary` | — | `{total_minor, by_category[], by_day[], count}` |
| GET | `/projects/{id}/report/export.csv` | — | `text/csv` stream |
| GET | `/projects/{id}/report/export.xlsx` | — | `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` |
| POST | `/invites` | `{project_id?, role, ttl_hours}` | `{token, url, expires_at}` |

OpenAPI schema автогенерится FastAPI на `/api/v1/docs`.

---

## 11. Security & secrets

**Что приватно:**
- `.env` (telegram bot token, MIMO_API_KEY, GOOGLE_API_KEY, JWT_SECRET, DB password, MINIO_SECRET_KEY)
- Все production данные мамы (БД, MinIO bucket, бэкапы)
- `secrets/` и `data/` в `.gitignore`

**Что публично (github.com/kudnever/stager):**
- Весь код (MIT)
- `.env.example` с placeholder-значениями
- Docker Compose файлы для dev
- README, ARCHITECTURE, миграции, тесты

**Отдельный private repo:** `kudnever/stager-deploy` — production compose overrides + Caddyfile + бэкап скрипты + Tailscale конфиг. Туда же — данные клиентов мамы если будут (но в идеале они только в БД на сервере, не в git).

**Аутентификация:**
- Bot — telegram_id whitelist + invite-token redeem
- Web — JWT (HS256, secret в env, exp 7d), bcrypt для паролей
- Между сервисами — internal network Docker, нет публичной экспозиции postgres/redis/minio

**Rate-limit (basic, через middleware FastAPI):**
- `/auth/login` — 5/min/IP
- остальное — 60/min/JWT-sub

---

## 12. Test strategy (coverage target 60%)

| Слой | Что тестируем | Как |
|---|---|---|
| Models / migrations | upgrade head → downgrade -1 → upgrade head, FK constraints | pytest + testcontainers Postgres |
| Domain (categories, parsers) | парсинг `/add` строки, currency formatting, validation | юнит, без БД |
| LLM router | MiMo упал → Gemini подхватил; rate-limit → circuit-breaker | мокаем httpx через respx |
| Bot handlers | /start с токеном / без; photo→FSM cycle | aiogram TestClient + Telegram-mocks |
| Celery tasks | ocr_task с моком router; idempotency | apply_sync mode + fixture |
| REST API | auth flow, CRUD проектов и расходов, RBAC (нельзя чужой проект) | httpx AsyncClient + dependency override |
| Reports | CSV/XLSX generation побайтово, корректность сумм | snapshot tests |

CI запускает `make test` — поднимается testcontainers postgres + redis (in-memory заменой), прогоняет всё.

---

## 13. Deploy plan

### Compose структура (3 файла)

- `docker-compose.yml` — dev, всё локально, volumes наружу
- `docker-compose.prod.yml` — override: образы pinned, volumes именованные, restart policy, healthchecks, без портов наружу кроме Caddy
- `docker-compose.override.yml` — локальные тюнинги (в `.gitignore`)

### Сервисы

```yaml
services:
  postgres:    # 16-alpine, volume pgdata, healthcheck pg_isready
  redis:       # 7-alpine, volume redisdata
  minio:       # quay.io/minio/minio, volume miniodata, healthcheck /minio/health/live
  bot:         # build ./apps/bot, depends postgres+redis+minio healthy
  api:         # build ./apps/api, expose 8000 internal, depends postgres healthy
  worker:      # build ./apps/worker, depends redis+postgres+minio healthy
  beat:        # build ./apps/worker, command celery beat
  web:         # build ./apps/web (Next.js), expose 3000 internal
  caddy:       # caddy:2-alpine, ports 80:80 443:443, mounts Caddyfile
```

### Env vars (см. `.env.example`)

```
# Telegram
TELEGRAM_BOT_TOKEN=
TELEGRAM_WHITELIST_IDS=123456,789012   # initial admins, comma-separated
TELEGRAM_BOT_USERNAME=stager_bot       # для invite-ссылок

# DB / Redis / MinIO
POSTGRES_USER=stager
POSTGRES_PASSWORD=
POSTGRES_DB=stager
DATABASE_URL=postgresql+asyncpg://stager:${POSTGRES_PASSWORD}@postgres:5432/stager
REDIS_URL=redis://redis:6379/0
MINIO_ROOT_USER=stager
MINIO_ROOT_PASSWORD=
MINIO_BUCKET=stager-receipts
MINIO_ENDPOINT=http://minio:9000

# LLM
MIMO_API_KEY=
MIMO_BASE_URL=https://token-plan-sgp.xiaomimimo.com/v1
GOOGLE_API_KEY=
LLM_DEFAULT_VISION_PROVIDER=mimo
LLM_DEFAULT_TEXT_PROVIDER=mimo

# Auth
JWT_SECRET=
JWT_EXP_HOURS=168

# Observability
SENTRY_DSN=
LOG_LEVEL=INFO

# Web
NEXT_PUBLIC_API_BASE=/api/v1
```

### Healthchecks

- `bot`: pings Telegram getMe + Redis PING каждые 30s
- `api`: `GET /health` → `{db: ok, redis: ok}`
- `worker`: Celery `ping` через `celery -A app inspect ping`
- `web`: `GET /api/health`

### Миграции

При деплое: `docker compose run --rm api alembic upgrade head` ДО запуска bot/api/worker. В CI same.

### Caddy

```
stager.kudnever.dev {
    reverse_proxy /api/* api:8000
    reverse_proxy web:3000
}
```

(полный Caddyfile в private deploy-repo)

### Бэкапы (cron, отдельный скрипт)

- `pg_dump` ежедневно в 04:00 → `/var/backups/stager/pg-YYYY-MM-DD.sql.gz` (хранить 7 дней)
- MinIO `mc mirror` еженедельно

---

## 14. Что НЕ в MVP

Полностью отложено в extension scope: PDF client report, items/rental_periods + return-date алерты, collaborator invite UI в web, Grafana, mimo-v2.5-tts, mobile, монетизация, налоговая compliance.

---

## 15. Открытые вопросы — РАЗРЕШЕНО

| # | Вопрос | Решение |
|---|---|---|
| 1 | Имя проекта | **Stager** (оставляем) |
| 2 | Hosting | Тот же Hetzner. На сервере 2.9Gi RAM свободно, Stager budget ~1.5Gi |
| 3 | Whitelist | Whitelist (env initial admins) + invite-токены для всех остальных |
| 4 | Валюты | Одна валюта на проект, immutable, RUB default |
| 5 | Категории OCR | Fixed enum из 10 ключей, LLM выбирает один |
