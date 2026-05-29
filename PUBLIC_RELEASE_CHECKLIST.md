# Чек-лист перед `git push` в public

Stager is a public portfolio repo. Production secrets, real user data, server IPs, and deployment-only paths stay outside git. Run this checklist before each public release.

## Что проверить локально (один раз перед `git init` + push)

```bash
# 1. .gitignore работает — этих файлов НЕ должно быть в `git status`:
#    .env, .env.local, .env.production, secrets/, data/, *.sqlite

# 2. Никаких реальных токенов в трекаемых файлах:
grep -rE "(7[0-9]{9}:|AIza[0-9A-Za-z\\-_]{35})" --include="*.py" --include="*.ts" --include="*.tsx" --include="*.yml" --include="*.yaml" --include="*.json" .
# должно вернуть пусто (или только в .env.example как placeholder)

# 3. Никаких реальных telegram_id пользователей в коде:
grep -rE "TELEGRAM_WHITELIST_IDS=[0-9]" .
# должно быть только в .env.example (пустое) и docs

# 4. seed_dev.py не содержит реальных имён клиентов / адресов:
cat scripts/seed_dev.py | grep -E "(кв\.|Парнас|клиент)"  # рабочие плейсхолдеры — ок
```

## Что НЕ коммитить никогда

- `.env*` (кроме `.env.example`)
- бэкапы БД: `*.sql.gz`, `pg_dump*`
- фотографии чеков: `data/`, `backups/`, `*.jpg`, `*.png`
- production Compose с реальными host-mounts, IP, доменами и backup paths

## Что хранится приватно

Туда уходит:
- production overrides с правильными volumes и `restart: always`
- Caddyfile или reverse-proxy config с реальным доменом
- `.env.production` (gitignored даже в private repo — храним в Bitwarden / 1Password)
- `scripts/backup.sh` с конкретным путём `/var/backups/stager/`
- `scripts/restore.sh`

Public repo не раскрывает реальные IP, домены, host paths или имена production-пользователей.

## Что обязательно ДОЛЖНО быть в public репо

Без этих файлов проект хуже проверяется ревьюером.

- [x] [README.md](README.md) с архитектурной картинкой и badge'ом CI
- [x] [ARCHITECTURE.md](ARCHITECTURE.md), [ROADMAP.md](ROADMAP.md), [REPO_STRUCTURE.md](REPO_STRUCTURE.md)
- [x] [LICENSE](LICENSE) (MIT)
- [x] [.env.example](.env.example) с ВСЕМИ ключами и комментариями
- [x] CI workflow ([.github/workflows/ci.yml](.github/workflows/ci.yml))
- [x] Тесты с coverage 60%+
- [x] [README-user.ru.md](README-user.ru.md) — отдельная инструкция для конечного пользователя

## Финальная команда

```bash
# Когда всё проверил:
cd <repo>
git init
git add .
git status   # глазами просмотри ещё раз!
git commit -m "feat: initial public release — MVP scaffolding (Days 1-10)"
gh repo create IliaMalkin/stager --public --source=. --remote=origin --push --description "Multi-tenant project expense tracker — Telegram bot + Next.js admin"
```
