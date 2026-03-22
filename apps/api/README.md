# Dental Clinic API

FastAPI backend starter for website and automation platform. It includes sync SQLAlchemy 2.0 setup, Alembic migrations, PostgreSQL support, Docker tooling, and a basic health endpoint.

## Setup

Copy the environment template:

```bash
cp .env.example .env
```

Install dependencies locally:

```bash
pip install -e .[dev]
```

## Local development

Recommended workflow:

- run PostgreSQL as a local system service
- run the FastAPI app locally with auto-reload

If you run the API locally, point `.env` at your local PostgreSQL instance:

```env
DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/dental_clinic
```

Make sure PostgreSQL is running, then start the API with auto-reload:

```bash
uvicorn app.main:app --reload
```

The health check will be available at `http://localhost:8000/health`.

## Production

The production deployment runs the API in Docker. `Caddy` proxies the public
domain `https://api.dental-clinic.kiremma.dev` to the internal `api:8000`
service in `docker-compose.prod.yml`.

Expected production flow:

- host PostgreSQL runs on the VPS
- the API container reads environment variables passed from `docker-compose.prod.yml`
- the API container connects to host PostgreSQL through `172.30.0.1:5432`
- `Caddy` reverse proxies `api.dental-clinic.kiremma.dev` to `api:8000`

The health check will be available at:

- `https://api.dental-clinic.kiremma.dev/health`
- `http://api:8000/health` inside the production Docker network

## Run everything with Docker Compose

`docker-compose.yml` now contains only supporting services. They connect to the
host machine PostgreSQL instance through `host.docker.internal`.

To start the supporting services:

```bash
docker compose up -d
```

This starts `Directus` and `n8n`.

## Alembic migrations

Create a migration:

```bash
alembic revision --autogenerate -m "init"
```

Apply migrations:

```bash
alembic upgrade head
```

Seed sample data:

```bash
python scripts/seed_db.py
```

Clear application data while keeping Alembic history:

```bash
python scripts/clear_db.py
```

## Tests

Run the test suite:

```bash
pytest
```
