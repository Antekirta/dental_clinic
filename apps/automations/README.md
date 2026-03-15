# Automations

This folder contains the local `n8n` runtime data for the dental clinic project.

## Run

From the repository root:

```powershell
docker compose up -d n8n
```

Then open [http://localhost:5678](http://localhost:5678).

## Webhook testing with clouflared

Run `n8n` locally first, then expose it with `clouflared`:

```powershell
clouflared tunnek run n8n-tunnel
```

Copy the public HTTPS URL https://n8n.kiremma.dev/, then set it as `N8N_WEBHOOK_URL` in the root `.env`:

```env
N8N_WEBHOOK_URL=https://n8n.kiremma.dev/
```

Restart `n8n` after changing the env:

```powershell
docker compose up -d n8n
```

Use the `https://n8n.kiremma.dev/` URL for incoming webhooks. Keep `N8N_EDITOR_BASE_URL` pointed at `http://localhost:5678` so the editor stays local.

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
