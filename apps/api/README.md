# Dental Clinic API

FastAPI backend starter for the dental clinic website and automation platform. It includes sync SQLAlchemy 2.0 setup, Alembic migrations, PostgreSQL support, Docker tooling, and a basic health endpoint.

## Setup

Copy the environment template:

```bash
cp .env.example .env
```

Install dependencies locally:

```bash
pip install -e .[dev]
```

## Run locally

Start the API with auto-reload:

```bash
uvicorn app.main:app --reload
```

The health check will be available at `http://localhost:8000/health`.

## Run with Docker Compose

```bash
docker compose up --build
```

This starts:

- `api` on port `8000`
- `db` on port `5432`

## Alembic migrations

Create a migration:

```bash
alembic revision --autogenerate -m "init"
```

Apply migrations:

```bash
alembic upgrade head
```

## Tests

Run the test suite:

```bash
pytest
```
