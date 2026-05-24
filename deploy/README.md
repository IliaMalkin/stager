# Production deploy

Эти файлы — public. Реальные секреты живут в private repo `kudnever/stager-deploy` и в `.env.production` на сервере.

## Первичная установка на Hetzner (ubuntu-4gb-nbg1-2, 178.105.163.2)

```bash
# 1. Поставить Docker если нет (есть — пропусти)
ssh root@178.105.163.2
docker --version  # должно быть 29+

# 2. Клонировать
mkdir -p /opt/stager && cd /opt/stager
git clone https://github.com/kudnever/stager.git .

# 3. Положить .env.production (в репо его НЕТ — копируем руками)
scp .env.production root@178.105.163.2:/opt/stager/.env

# 4. DNS: добавить A-запись stager.kudnever.dev → 178.105.163.2

# 5. Запустить
cd /opt/stager
docker compose -f docker-compose.yml -f docker-compose.prod.yml build
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d postgres redis minio

# Ждём 10 сек, миграции
docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm api alembic upgrade head

# Создаём admin для web
docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm api \
    python -m apps.api.cli create-admin ilyamalkinn@gmail.com '<password>' 'Ilia'

# Поднимаем всё остальное
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# 6. Бэкап cron
sudo cp deploy/backup.sh /etc/cron.daily/stager-backup
sudo chmod +x /etc/cron.daily/stager-backup
```

## Smoke test после deploy

```bash
curl -s https://stager.kudnever.dev/health
curl -s https://stager.kudnever.dev/api/v1/docs   # 200, html
# Telegram: /start твоим botid'ом — должно ответить
```

## Откат

```bash
# Если миграция сломала — даунгрейд:
docker compose ... run --rm api alembic downgrade -1

# Полный откат — checkout предыдущего тега + пересобрать
git checkout v0.1.0
docker compose ... up -d --build
```

## Где смотреть логи

- `docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f bot api worker`
- Sentry dashboard (если DSN задан в .env)
- Caddy access logs: `docker compose ... logs caddy`
