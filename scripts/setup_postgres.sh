#!/usr/bin/env sh
set -eu

ENV_FILE="${ENV_FILE:-./env.prod}"

log() {
  printf '%s\n' "$*"
}

fail() {
  printf 'Error: %s\n' "$*" >&2
  exit 1
}

sudo_run() {
  if command -v sudo >/dev/null 2>&1; then
    sudo "$@"
  else
    "$@"
  fi
}

psql_super() {
  sudo_run -u postgres psql -v ON_ERROR_STOP=1 -d postgres "$@"
}

load_env_file() {
  [ -f "$ENV_FILE" ] || fail "Env file not found: $ENV_FILE"

  set -a
  # shellcheck disable=SC1090
  . "$ENV_FILE"
  set +a
}

validate_required_vars() {
  : "${POSTGRES_DB:?POSTGRES_DB is required in $ENV_FILE}"
  : "${POSTGRES_APP_USER:?POSTGRES_APP_USER is required in $ENV_FILE}"
  : "${POSTGRES_APP_PASSWORD:?POSTGRES_APP_PASSWORD is required in $ENV_FILE}"
}

validate_identifier() {
  value="$1"
  name="$2"

  case "$value" in
    *[!a-zA-Z0-9_]*|'')
      fail "$name contains invalid characters. Use only letters, digits, and underscore."
      ;;
  esac
}

escape_sql_literal() {
  printf "%s" "$1" | sed "s/'/''/g"
}

ensure_psql_exists() {
  command -v psql >/dev/null 2>&1 || fail "psql not found. Install PostgreSQL first."
}

ensure_role() {
  log "Ensuring PostgreSQL role exists: ${POSTGRES_APP_USER}"

  role_exists="$(psql_super -tAc "SELECT 1 FROM pg_roles WHERE rolname='${POSTGRES_APP_USER}'" | tr -d '[:space:]')"
  escaped_password="$(escape_sql_literal "$POSTGRES_APP_PASSWORD")"

  if [ "$role_exists" = "1" ]; then
    log "Role exists, updating password"
    psql_super -c "ALTER ROLE ${POSTGRES_APP_USER} WITH LOGIN PASSWORD '${escaped_password}';"
  else
    log "Creating role"
    psql_super -c "CREATE ROLE ${POSTGRES_APP_USER} WITH LOGIN PASSWORD '${escaped_password}';"
  fi
}

ensure_database() {
  log "Ensuring database exists: ${POSTGRES_DB}"

  db_exists="$(psql_super -tAc "SELECT 1 FROM pg_database WHERE datname='${POSTGRES_DB}'" | tr -d '[:space:]')"

  if [ "$db_exists" = "1" ]; then
    log "Database exists, ensuring owner"
    psql_super -c "ALTER DATABASE ${POSTGRES_DB} OWNER TO ${POSTGRES_APP_USER};"
  else
    log "Creating database"
    psql_super -c "CREATE DATABASE ${POSTGRES_DB} OWNER ${POSTGRES_APP_USER};"
  fi
}

print_result() {
  postgres_port="${POSTGRES_PORT:-5432}"

  log ""
  log "Done."
  log "Database: ${POSTGRES_DB}"
  log "PostgreSQL user: ${POSTGRES_APP_USER}"
  log "Port: ${postgres_port}"
  log ""
  log "DATABASE_URL:"
  log "postgresql+psycopg2://${POSTGRES_APP_USER}:${POSTGRES_APP_PASSWORD}@localhost:${postgres_port}/${POSTGRES_DB}"
}

main() {
  load_env_file
  validate_required_vars
  validate_identifier "$POSTGRES_DB" "POSTGRES_DB"
  validate_identifier "$POSTGRES_APP_USER" "POSTGRES_APP_USER"
  ensure_psql_exists
  ensure_role
  ensure_database
  print_result
}

main "$@"