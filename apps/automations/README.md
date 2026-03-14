# Automations

This folder contains the local `n8n` runtime data for the dental clinic project.

## Run

From the repository root:

```powershell
docker compose up -d n8n
```

Then open [http://localhost:5678](http://localhost:5678).

## Storage

- `apps/automations/.n8n` stores the `n8n` database and credentials for local development.
- `apps/automations/files` is mounted to `/files` inside the container for workflow file access.

## Optional env

The root `.env` can override:

- `N8N_HOST`
- `N8N_PORT`
- `N8N_PROTOCOL`
- `N8N_EDITOR_BASE_URL`
- `N8N_WEBHOOK_URL`
- `N8N_TIMEZONE`
