# Production Runbook

This repository now includes a standalone production stack for `Directus` and
`n8n`:

- `docker-compose.prod.yml` - production-only services
- `Caddyfile` - HTTPS termination and reverse proxy

The production stack assumes:

- PostgreSQL already exists outside Docker
- only Caddy is exposed publicly on ports `80` and `443`

## 1. DNS

Create two DNS records pointing at the droplet:

- `cms.dental-clinic.kiremma.dev`
- `n8n.dental-clinic.kiremma.dev`

## 2. Server-side env file

Do not reuse the repository `.env` files as the deployed source of truth.
Create a separate env file on the server, for example:

```text
/etc/dental-clinic/directus-n8n.env
```

Required variables:

```env
LETSENCRYPT_EMAIL=ops@your-domain.com

DIRECTUS_IMAGE_TAG=11.8.0

DIRECTUS_KEY=replace_me
DIRECTUS_SECRET=replace_me
DIRECTUS_DB_CLIENT=pg
DIRECTUS_DB_HOST=10.17.0.5
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
N8N_DB_HOST=10.17.0.5
N8N_DB_PORT=5432
N8N_DB_DATABASE=n8n
N8N_DB_USER=n8n
N8N_DB_PASSWORD=replace_me
N8N_ENCRYPTION_KEY=replace_with_a_long_random_value
```

Notes:

- `n8n` is pinned in `docker-compose.prod.yml`. Update the image tag there when
  you deliberately upgrade it.
- `DIRECTUS_DB_HOST` and `N8N_DB_HOST` must point to the external PostgreSQL
  host, not `host.docker.internal`.
- `n8n` should have its own database, separate from the clinic application
  schema.

## 3. Start the stack

From the repository root:

```powershell
docker compose --env-file /etc/dental-clinic/directus-n8n.env -f docker-compose.prod.yml up -d
```

To pull newer pinned images before restart:

```powershell
docker compose --env-file /etc/dental-clinic/directus-n8n.env -f docker-compose.prod.yml pull
docker compose --env-file /etc/dental-clinic/directus-n8n.env -f docker-compose.prod.yml up -d
```

## 4. Firewall

Allow inbound traffic only for:

- `80/tcp`
- `443/tcp`

Do not expose `8055` or `5678` publicly.

## 5. Persistence

These paths remain persisted on the host:

- `apps/cms/uploads`
- `apps/cms/extensions`
- `apps/automations/.n8n`
- `apps/automations/files`

## 6. Recommended hardening

- Restrict access to `n8n` editor with Cloudflare Access, VPN, or IP allowlist.
- Rotate any secrets that were previously committed to local env files.
- Back up the external PostgreSQL databases and the `uploads` directory.
