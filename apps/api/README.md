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

- run PostgreSQL in Docker
- run the FastAPI app locally with auto-reload

If you run the API locally, update `.env` so the database host points to `localhost` instead of the Docker service name:

```env
DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/dental_clinic
```

Start PostgreSQL only:

```bash
docker compose up db -d
```

Start the API with auto-reload:

```bash
uvicorn app.main:app --reload
```

The health check will be available at `http://localhost:8000/health`.

## Run everything with Docker Compose

If you want the API and PostgreSQL to run in containers together, keep the default `.env.example` database host (`db`) and run:

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
