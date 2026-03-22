# Local Development

## One-Time Setup

### 1. PostgreSQL
Open `SQL Shell (psql)` from the Start menu, accept the defaults, and enter the password for the `postgres` user.

Create the database:

```sql
CREATE DATABASE dental_clinic;
```

### 2. Root `.env`
Fill in the root [`.env`](D:/projects/dental_clinic/.env) with variables for local development.

Minimum required:

```env
APP_NAME=Dental Clinic API
APP_ENV=development
APP_DEBUG=true
APP_HOST=0.0.0.0
APP_PORT=8000

POSTGRES_DB=dental_clinic
POSTGRES_USER=postgres
POSTGRES_PASSWORD=YOUR_DB_PASSWORD
DATABASE_URL=postgresql+psycopg2://postgres:YOUR_DB_PASSWORD@localhost:5432/dental_clinic

DIRECTUS_KEY=somelongrandomkey
DIRECTUS_SECRET=anotherlongrandomkey
DIRECTUS_DB_CLIENT=pg
DIRECTUS_DB_HOST=host.docker.internal
DIRECTUS_DB_PORT=5432
DIRECTUS_DB_DATABASE=dental_clinic
DIRECTUS_DB_USER=postgres
DIRECTUS_DB_PASSWORD=YOUR_DB_PASSWORD
DIRECTUS_ADMIN_EMAIL=admin@dental-clinic.kiremma.dev
DIRECTUS_ADMIN_PASSWORD=YOUR_DIRECTUS_PASSWORD
DIRECTUS_PUBLIC_URL=http://localhost:8055
DIRECTUS_WEBSOCKETS_ENABLED=true
DIRECTUS_CORS_ENABLED=true
DIRECTUS_CORS_ORIGIN=true

N8N_HOST=localhost
N8N_PORT=5678
N8N_PROTOCOL=http
N8N_EDITOR_BASE_URL=http://localhost:5678
N8N_WEBHOOK_URL=https://n8n.kiremma.dev/
N8N_TIMEZONE=Europe/London
```

### 3. API: virtualenv, dependencies, migrations, seed
From the project root:

```powershell
cd D:\projects\dental_clinic\apps\api
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -e .[dev]
alembic upgrade head
python scripts\seed_db.py
```

### 4. DBeaver
Connect to the local database with:

- host: `localhost`
- port: `5432`
- database: `dental_clinic`
- user: `postgres`
- password: your local `postgres` password

### 5. Directus
From the project root:

```powershell
cd D:\projects\dental_clinic
docker compose up -d directus
```

Open `http://localhost:8055`.

Generate a static token:

- `User Directory`
- `Administrator`
- scroll down
- `Generate token`

Make the required collections visible:

- `Settings`
- `Data Model`

### 6. Astro env
Create or fill [`D:\projects\dental_clinic\apps\web\.env`](D:/projects/dental_clinic/apps/web/.env):

```env
DIRECTUS_URL=http://localhost:8055
DIRECTUS_STATIC_TOKEN=YOUR_DIRECTUS_TOKEN
```

### 7. n8n
From the project root:

```powershell
cd D:\projects\dental_clinic
docker compose up -d n8n
```

If external webhooks are needed, start a tunnel:

```powershell
cd D:\
cd Apps
.\cloudflared.exe tunnel run n8n-tunnel
```

Before that, check `~/.cloudflared/config.yml`.

## Daily Run

### Start local services
From the project root:

```powershell
cd D:\projects\dental_clinic
docker compose up -d
```

This starts `Directus` and `n8n`.

### Start API
In a separate terminal:

```powershell
cd D:\projects\dental_clinic\apps\api
.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

API will be available at:

- `http://localhost:8000/health`

### Start Astro
In a separate terminal:

```powershell
cd D:\projects\dental_clinic\apps\web
npm run dev
```

### If migrations changed

```powershell
cd D:\projects\dental_clinic\apps\api
.venv\Scripts\Activate.ps1
alembic upgrade head
```

### If seed data must be reapplied

```powershell
cd D:\projects\dental_clinic\apps\api
.venv\Scripts\Activate.ps1
python scripts\seed_db.py
```
