# Production deploy

These files are public. Keep real secrets, server IPs, hostnames, and
production-only overrides outside this repository.

## Initial setup on a VPS

```bash
# 1. Install Docker if needed.
ssh root@<server-ip>
docker --version

# 2. Clone the repository.
mkdir -p /opt/stager && cd /opt/stager
git clone https://github.com/kudnever/stager.git .

# 3. Copy the production env file. Do not commit it.
scp .env.production root@<server-ip>:/opt/stager/.env

# 4. DNS: point your app domain at the server.

# 5. Start the stack.
cd /opt/stager
docker compose -f docker-compose.yml -f docker-compose.prod.yml build
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d postgres redis minio

# Apply migrations.
docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm api alembic upgrade head

# Create the first web admin.
docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm api \
    python -m apps.api.cli create-admin '<admin-email>' '<password>' '<full-name>'

# Start everything else.
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# 6. Backup cron.
sudo cp deploy/backup.sh /etc/cron.daily/stager-backup
sudo chmod +x /etc/cron.daily/stager-backup
```

## Smoke test after deploy

```bash
curl -s https://<app-domain>/health
curl -s https://<app-domain>/api/v1/docs
# Telegram: /start should receive a bot response.
```

## Rollback

```bash
# If a migration breaks:
docker compose ... run --rm api alembic downgrade -1

# Full rollback: checkout the previous tag and rebuild.
git checkout v0.1.0
docker compose ... up -d --build
```

## Logs

- `docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f bot api worker`
- Sentry dashboard, if `SENTRY_DSN` is configured.
- Caddy access logs: `docker compose ... logs caddy`
