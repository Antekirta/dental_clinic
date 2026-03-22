# Production Deployment

## One-Time Setup

### 1. VPS: code and Python environment
On the server:

```bash
ssh kiremma

sudo apt update
sudo apt install -y python3 python3-venv python3-pip

mkdir -p ~/apps
cd ~/apps
git clone <repo-url> dental_clinic

cd ~/apps/dental_clinic/apps/api
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e .
```

### 2. Upload production env
On the local machine:

```bash
cd /d/project/dental_clinic
scp .env.prod kiremma:~/apps/dental_clinic/.env.prod
```

The server env file must contain at least:

```env
POSTGRES_DB=dental_clinic
POSTGRES_USER=deploy
POSTGRES_PASSWORD=...

LETSENCRYPT_EMAIL=...

APP_NAME=Dental Clinic API
APP_ENV=production
APP_DEBUG=false
APP_HOST=0.0.0.0
APP_PORT=8000

DIRECTUS_IMAGE_TAG=11.8.0
DIRECTUS_KEY=...
DIRECTUS_SECRET=...
DIRECTUS_DB_CLIENT=pg
DIRECTUS_DB_HOST=172.30.0.1
DIRECTUS_DB_PORT=5432
DIRECTUS_DB_DATABASE=dental_clinic
DIRECTUS_DB_USER=deploy
DIRECTUS_DB_PASSWORD=...
DIRECTUS_ADMIN_EMAIL=admin@kiremma.dev
DIRECTUS_ADMIN_PASSWORD=...
DIRECTUS_PUBLIC_URL=https://cms.dental-clinic.kiremma.dev
DIRECTUS_WEBSOCKETS_ENABLED=true
DIRECTUS_CORS_ENABLED=true
DIRECTUS_CORS_ORIGIN=https://dental-clinic.kiremma.dev,https://cms.dental-clinic.kiremma.dev

N8N_HOST=n8n.dental-clinic.kiremma.dev
N8N_PROTOCOL=https
N8N_EDITOR_BASE_URL=https://n8n.dental-clinic.kiremma.dev
N8N_WEBHOOK_URL=https://n8n.dental-clinic.kiremma.dev
N8N_TIMEZONE=Europe/London
N8N_ENCRYPTION_KEY=...
```

### 3. Configure host PostgreSQL for the production Docker network
On the server:

```bash
sudo apt install -y postgresql postgresql-client

cd ~/apps/dental_clinic
sudo sh ./scripts/setup_postgres.sh
```

If `ufw` is active, allow the production Docker subnet to reach PostgreSQL:

```bash
sudo ufw allow from 172.30.0.0/24 to any port 5432 proto tcp
sudo ufw reload
```

### 4. Prepare persisted directories
On the server:

```bash
cd ~/apps/dental_clinic
sudo mkdir -p apps/cms/uploads apps/cms/extensions apps/automations/.n8n apps/automations/files
sudo chown -R 1000:1000 apps/cms/uploads apps/cms/extensions apps/automations/.n8n apps/automations/files
sudo chmod -R u+rwX,go-rwx apps/cms/uploads apps/cms/extensions apps/automations/.n8n apps/automations/files
```

### 5. Start API / Directus / n8n / Caddy
On the server, from the repository root:

```bash
cd ~/apps/dental_clinic
docker compose --env-file .env.prod -f docker-compose.prod.yml pull
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build
```

Smoke-test the database from the production Docker network:

```bash
docker run --rm --network dental_clinic_edge \
  -e PGPASSWORD='YOUR_POSTGRES_PASSWORD' \
  postgres:16-alpine \
  psql -h 172.30.0.1 -U deploy -d dental_clinic -p 5432 -c '\conninfo'
```

Check:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml ps
docker compose --env-file .env.prod -f docker-compose.prod.yml logs --tail=100 api
docker compose --env-file .env.prod -f docker-compose.prod.yml logs --tail=100 directus
docker compose --env-file .env.prod -f docker-compose.prod.yml logs --tail=100 n8n
docker compose --env-file .env.prod -f docker-compose.prod.yml exec caddy sh -lc "wget -S -O- http://directus:8055/server/health || true"
docker compose --env-file .env.prod -f docker-compose.prod.yml exec caddy sh -lc "wget -S -O- http://api:8000/health || true"
```

### 6. Cloudflare Pages
On the local machine:

```bash
cd /d/project/dental_clinic/apps/web
npm i
npx wrangler pages project create dental-clinic
```

In Cloudflare Pages, one time:

- add custom domain `dental-clinic.kiremma.dev`

### 7. Directus token for Astro
One time:

- open `https://cms.dental-clinic.kiremma.dev`
- `User Directory` -> `Administrator` -> `Generate token`

Then add these secrets in Cloudflare:

```env
DIRECTUS_URL=https://cms.dental-clinic.kiremma.dev
DIRECTUS_STATIC_TOKEN=TOKEN
```

## Regular Release

### If backend / DB / Directus / Caddy changed
On the server:

```bash
ssh kiremma
cd ~/apps/dental_clinic
git pull origin master
```

If Python dependencies changed:

```bash
cd ~/apps/dental_clinic/apps/api
source .venv/bin/activate
pip install -e .
```

If backend code changed:

```bash
cd ~/apps/dental_clinic
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build api
```

If migrations changed:

```bash
cd ~/apps/dental_clinic/apps/api
source .venv/bin/activate
set -a
source ~/apps/dental_clinic/.env.prod
set +a
alembic upgrade head
```

If any `POSTGRES_*` values changed, rerun the host PostgreSQL setup:

```bash
cd ~/apps/dental_clinic
sudo sh ./scripts/setup_postgres.sh
```

Refresh the production containers:

```bash
cd ~/apps/dental_clinic
docker compose --env-file .env.prod -f docker-compose.prod.yml pull
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build
```

Check:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml ps
docker compose --env-file .env.prod -f docker-compose.prod.yml logs --tail=100 api
docker compose --env-file .env.prod -f docker-compose.prod.yml logs --tail=100 directus
docker compose --env-file .env.prod -f docker-compose.prod.yml logs --tail=100 n8n
```

### If only frontend changed
On the local machine:

```bash
cd /d/project/dental_clinic/apps/web
npm i
npm run build --mode=prod
npx wrangler pages deploy dist
```

### DB access via DBeaver
On the local machine:

```bash
ssh -L 55432:localhost:5432 kiremma
```

Then connect to:

- host: `localhost`
- port: `55432`
