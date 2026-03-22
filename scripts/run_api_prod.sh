#!/usr/bin/env sh
set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
APP_DIR="$PROJECT_ROOT/apps/api"
ENV_FILE="${ENV_FILE:-$PROJECT_ROOT/.env.prod}"
PYTHON_BIN="${PYTHON_BIN:-$APP_DIR/.venv/bin/python}"

log() {
  printf '%s\n' "$*"
}

fail() {
  printf 'Error: %s\n' "$*" >&2
  exit 1
}

[ -f "$ENV_FILE" ] || fail "Env file not found: $ENV_FILE"
[ -x "$PYTHON_BIN" ] || fail "Python executable not found: $PYTHON_BIN"

set -a
# shellcheck disable=SC1090
. "$ENV_FILE"
set +a

cd "$APP_DIR"

log "Starting FastAPI on ${APP_HOST:-0.0.0.0}:${APP_PORT:-8000}"
exec "$PYTHON_BIN" -m uvicorn app.main:app --host "${APP_HOST:-0.0.0.0}" --port "${APP_PORT:-8000}"
