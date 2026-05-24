# Чек-лист перед `git push` в public

Стейджер задумывается как open-source CV-кейс. Данные мамы и production-секреты живут отдельно. Пройдись по этому списку перед каждым публичным релизом.

## Что проверить локально (один раз перед `git init` + push)

```bash
# 1. .gitignore работает — этих файлов НЕ должно быть в `git status`:
#    .env, .env.local, .env.production, secrets/, data/, *.sqlite

# 2. Никаких реальных токенов в трекаемых файлах:
grep -rE "(7[0-9]{9}:|AIza[0-9A-Za-z\\-_]{35})" --include="*.py" --include="*.ts" --include="*.tsx" --include="*.yml" --include="*.yaml" --include="*.json" .
# должно вернуть пусто (или только в .env.example как placeholder)

# 3. Никаких telegram_id мамы или знакомых в коде:
grep -rE "TELEGRAM_WHITELIST_IDS=[0-9]" .
# должно быть только в .env.example (пустое) и docs

# 4. seed_dev.py не содержит реальных имён клиентов / адресов:
cat scripts/seed_dev.py | grep -E "(кв\.|Парнас|клиент)"  # рабочие плейсхолдеры — ок
```

## Что НЕ коммитить никогда

- `.env*` (кроме `.env.example`)
- бэкапы БД: `*.sql.gz`, `pg_dump*`
- фотографии чеков: `data/`, `backups/`, `*.jpg`, `*.png`
- production Compose с реальными host-mounts: `docker-compose.prod.yml` с конкретными путями — храним в отдельном private repo `kudnever/stager-deploy`

## Что лежит в private repo (`kudnever/stager-deploy`)

Создашь его руками после Day 12. Туда уходит:
- `docker-compose.prod.yml` с правильными volumes и `restart: always`
- `Caddyfile` с реальным доменом
- `.env.production` (gitignored даже в private repo — храним в Bitwarden / 1Password)
- `scripts/backup.sh` с конкретным путём `/var/backups/stager/`
- `scripts/restore.sh`

Public repo (`kudnever/stager`) ссылается на этот private как «отдельный deploy repo» в README, без раскрытия содержимого.

## Что обязательно ДОЛЖНО быть в public репо

Это и есть CV-сигнал — без этих файлов проект не воспринимается серьёзно.

- [x] [README.md](README.md) с архитектурной картинкой и badge'ом CI
- [x] [ARCHITECTURE.md](ARCHITECTURE.md), [ROADMAP.md](ROADMAP.md), [REPO_STRUCTURE.md](REPO_STRUCTURE.md)
- [x] [LICENSE](LICENSE) (MIT)
- [x] [.env.example](.env.example) с ВСЕМИ ключами и комментариями
- [x] CI workflow с зелёным статусом ([.github/workflows/ci.yml](.github/workflows/ci.yml))
- [x] Тесты с coverage 60%+
- [x] [README-mom.ru.md](README-mom.ru.md) — отдельная инструкция для мамы (показывает что проект реальный, не учебный)

## Финальная команда

```bash
# Когда всё проверил:
cd C:\Users\V\Documents\Claude\Stager
git init
git add .
git status   # глазами просмотри ещё раз!
git commit -m "feat: initial public release — MVP scaffolding (Days 1-10)"
gh repo create kudnever/stager --public --source=. --remote=origin --push --description "Multi-tenant project expense tracker — Telegram bot + Next.js admin"
```
