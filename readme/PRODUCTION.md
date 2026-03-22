# Production Runbook

This repository uses a host PostgreSQL instance plus a production-only Docker
stack for:

- `FastAPI`
- `Directus`
- `n8n`
- `Caddy`

Files involved:

- `docker-compose.prod.yml` - production services
- `Caddyfile` - HTTPS termination and reverse proxy
- `scripts/setup_postgres.sh` - host PostgreSQL bootstrap for the production Docker network

Production assumptions:

- PostgreSQL runs on the VPS host, outside Docker
- FastAPI runs in Docker
- only Caddy is exposed publicly on `80` and `443`
- the production Docker network is fixed to `172.30.0.0/24`
- containers reach the host PostgreSQL through the Docker bridge gateway `172.30.0.1`
- the API container reaches host PostgreSQL through `172.30.0.1:5432`
- `n8n` uses its built-in SQLite database persisted on the host

## 1. DNS

Create two DNS records pointing at the droplet:

- `api.dental-clinic.kiremma.dev`
- `cms.dental-clinic.kiremma.dev`
- `n8n.dental-clinic.kiremma.dev`

## 2. Server-side env file

Use the repository root production env file on the server:

```text
~/apps/dental_clinic/.env.prod
```

Required variables:

```env
POSTGRES_DB=dental_clinic
POSTGRES_USER=deploy
POSTGRES_PASSWORD=replace_me

LETSENCRYPT_EMAIL=ops@your-domain.com

APP_NAME=Dental Clinic API
APP_ENV=production
APP_DEBUG=false
APP_HOST=0.0.0.0
APP_PORT=8000

DIRECTUS_IMAGE_TAG=11.8.0

DIRECTUS_KEY=replace_me
DIRECTUS_SECRET=replace_me
DIRECTUS_DB_CLIENT=pg
DIRECTUS_DB_HOST=172.30.0.1
DIRECTUS_DB_PORT=5432
DIRECTUS_DB_DATABASE=dental_clinic
DIRECTUS_DB_USER=deploy
DIRECTUS_DB_PASSWORD=replace_me
DIRECTUS_ADMIN_EMAIL=admin@your-domain.com
DIRECTUS_ADMIN_PASSWORD=replace_me
DIRECTUS_PUBLIC_URL=https://cms.dental-clinic.kiremma.dev
DIRECTUS_WEBSOCKETS_ENABLED=true
DIRECTUS_CORS_ENABLED=true
DIRECTUS_CORS_ORIGIN=https://your-frontend-domain.com

N8N_HOST=n8n.dental-clinic.kiremma.dev
N8N_PROTOCOL=https
N8N_EDITOR_BASE_URL=https://n8n.dental-clinic.kiremma.dev
N8N_WEBHOOK_URL=https://n8n.dental-clinic.kiremma.dev
N8N_TIMEZONE=America/Sao_Paulo
N8N_ENCRYPTION_KEY=replace_with_a_long_random_value
```

Notes:

- `DIRECTUS_DB_HOST` must stay `172.30.0.1` for this production topology.
- `APP_HOST=0.0.0.0` is intentional inside the API container.
- Do not use `host.docker.internal` in production.
- Do not use ad-hoc VPS private IPs such as `10.x.x.x` in production docs or env files.
- `n8n` is pinned in `docker-compose.prod.yml` and uses its persisted SQLite data under `apps/automations/.n8n`.

## 3. Configure host PostgreSQL

Install PostgreSQL on the VPS if it is not already present, then run the setup
script from the repository root:

```bash
sudo apt update
sudo apt install -y postgresql postgresql-client

cd ~/apps/dental_clinic
sudo sh ./scripts/setup_postgres.sh
```

The script:

- ensures the PostgreSQL role and database exist
- ensures the application user owns the database
- configures `listen_addresses = '*'`
- adds a managed `pg_hba.conf` rule for `172.30.0.0/24`
- restarts PostgreSQL when required

If `ufw` is enabled on the VPS, allow the production Docker subnet to reach the
host PostgreSQL port:

```bash
sudo ufw allow from 172.30.0.0/24 to any port 5432 proto tcp
sudo ufw reload
```

## 4. Prepare persisted directories

Create the bind-mounted directories before the first start so Docker does not
create them with the wrong ownership, and make them writable for the container
user (`uid=1000`):

```bash
cd ~/apps/dental_clinic
sudo mkdir -p apps/cms/uploads apps/cms/extensions apps/automations/.n8n apps/automations/files
sudo chown -R 1000:1000 apps/cms/uploads apps/cms/extensions apps/automations/.n8n apps/automations/files
sudo chmod -R u+rwX,go-rwx apps/cms/uploads apps/cms/extensions apps/automations/.n8n apps/automations/files
```

## 5. Start the production stack

From the repository root:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml pull
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build
```

## 6. Validate the stack

Check containers and logs:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml ps
docker compose --env-file .env.prod -f docker-compose.prod.yml logs --tail=100 api
docker compose --env-file .env.prod -f docker-compose.prod.yml logs --tail=100 directus
docker compose --env-file .env.prod -f docker-compose.prod.yml logs --tail=100 n8n
```

Smoke-test PostgreSQL from the production Docker network:

```bash
docker run --rm --network dental_clinic_edge \
  -e PGPASSWORD=replace_me \
  postgres:16-alpine \
  psql -h 172.30.0.1 -U deploy -d dental_clinic -p 5432 -c '\conninfo'
```

Smoke-test Directus through the internal network:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml exec caddy sh -lc "wget -S -O- http://directus:8055/server/health || true"
```

Smoke-test FastAPI through the internal network:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml exec caddy sh -lc "wget -S -O- http://api:8000/health || true"
```

Public checks:

```bash
curl -fsS https://api.dental-clinic.kiremma.dev/health
curl -I https://cms.dental-clinic.kiremma.dev
curl -I https://n8n.dental-clinic.kiremma.dev
```

## 7. Firewall

Allow inbound traffic only for:

- `80/tcp`
- `443/tcp`

Do not expose `8055`, `5678`, or `5432` publicly.

Internal-only host ports reachable from the Docker subnet:

- `5432/tcp` for PostgreSQL

## 8. Persistence

These paths remain persisted on the host:

- `apps/cms/uploads`
- `apps/cms/extensions`
- `apps/automations/.n8n`
- `apps/automations/files`

## 9. Recommended hardening

- Restrict access to the `n8n` editor with Cloudflare Access, VPN, or IP allowlist.
- Rotate any secrets that were previously committed to local env files.
- Back up the PostgreSQL database and the persisted `uploads` / `n8n` directories.
