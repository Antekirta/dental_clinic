#!/usr/bin/env sh
set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="${ENV_FILE:-$SCRIPT_DIR/../.env.prod}"
POSTGRES_DOCKER_GATEWAY="${POSTGRES_DOCKER_GATEWAY:-172.30.0.1}"
POSTGRES_DOCKER_SUBNET="${POSTGRES_DOCKER_SUBNET:-172.30.0.0/24}"
POSTGRES_DOCKER_AUTH_METHOD="${POSTGRES_DOCKER_AUTH_METHOD:-scram-sha-256}"

MANAGED_CONF_BEGIN="# dental-clinic managed begin"
MANAGED_CONF_END="# dental-clinic managed end"
MANAGED_HBA_BEGIN="# dental-clinic managed hba begin"
MANAGED_HBA_END="# dental-clinic managed hba end"

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
  : "${POSTGRES_USER:?POSTGRES_USER is required in $ENV_FILE}"
  : "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required in $ENV_FILE}"
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

get_postgres_setting() {
  psql_super -tAc "SHOW $1" | sed 's/[[:space:]]*$//'
}

ensure_role() {
  log "Ensuring PostgreSQL role exists: ${POSTGRES_USER}"

  role_exists="$(psql_super -tAc "SELECT 1 FROM pg_roles WHERE rolname='${POSTGRES_USER}'" | tr -d '[:space:]')"
  escaped_password="$(escape_sql_literal "$POSTGRES_PASSWORD")"

  if [ "$role_exists" = "1" ]; then
    log "Role exists, updating password"
    psql_super -c "ALTER ROLE ${POSTGRES_USER} WITH LOGIN PASSWORD '${escaped_password}';"
  else
    log "Creating role"
    psql_super -c "CREATE ROLE ${POSTGRES_USER} WITH LOGIN PASSWORD '${escaped_password}';"
  fi
}

ensure_database() {
  log "Ensuring database exists: ${POSTGRES_DB}"

  db_exists="$(psql_super -tAc "SELECT 1 FROM pg_database WHERE datname='${POSTGRES_DB}'" | tr -d '[:space:]')"

  if [ "$db_exists" = "1" ]; then
    log "Database exists, ensuring owner"
    psql_super -c "ALTER DATABASE ${POSTGRES_DB} OWNER TO ${POSTGRES_USER};"
  else
    log "Creating database"
    psql_super -c "CREATE DATABASE ${POSTGRES_DB} OWNER ${POSTGRES_USER};"
  fi
}

ensure_public_schema_access() {
  log "Ensuring PostgreSQL schema access for ${POSTGRES_USER}"
  psql_super -d "${POSTGRES_DB}" -c "ALTER SCHEMA public OWNER TO ${POSTGRES_USER};"
  psql_super -d "${POSTGRES_DB}" -c "GRANT ALL ON SCHEMA public TO ${POSTGRES_USER};"
}

rewrite_file_with_managed_block() {
  file_path="$1"
  block_begin="$2"
  block_end="$3"
  block_body="$4"

  tmp_file="$(mktemp)"

  awk -v begin="$block_begin" -v end="$block_end" '
    $0 == begin { skip = 1; next }
    $0 == end { skip = 0; next }
    !skip { print }
  ' "$file_path" > "$tmp_file"

  {
    printf '\n%s\n' "$block_begin"
    printf '%s\n' "$block_body"
    printf '%s\n' "$block_end"
  } >> "$tmp_file"

  sudo_run cp "$tmp_file" "$file_path"
  rm -f "$tmp_file"
}

configure_postgresql_conf() {
  config_file="$(get_postgres_setting config_file)"
  [ -n "$config_file" ] || fail "Could not determine postgresql.conf path."

  log "Configuring listen_addresses in ${config_file}"
  rewrite_file_with_managed_block \
    "$config_file" \
    "$MANAGED_CONF_BEGIN" \
    "$MANAGED_CONF_END" \
    "listen_addresses = '*'"
}

configure_pg_hba() {
  hba_file="$(get_postgres_setting hba_file)"
  [ -n "$hba_file" ] || fail "Could not determine pg_hba.conf path."

  log "Configuring pg_hba.conf in ${hba_file}"
  rewrite_file_with_managed_block \
    "$hba_file" \
    "$MANAGED_HBA_BEGIN" \
    "$MANAGED_HBA_END" \
    "host    ${POSTGRES_DB}    ${POSTGRES_USER}    ${POSTGRES_DOCKER_SUBNET}    ${POSTGRES_DOCKER_AUTH_METHOD}"
}

restart_postgres() {
  if command -v pg_lsclusters >/dev/null 2>&1 && command -v pg_ctlcluster >/dev/null 2>&1; then
    pg_lsclusters --no-header | while read -r version cluster _rest; do
      [ -n "$version" ] || continue
      log "Restarting PostgreSQL cluster ${version}/${cluster}"
      sudo_run pg_ctlcluster "$version" "$cluster" restart
    done
    return
  fi

  if command -v systemctl >/dev/null 2>&1; then
    log "Restarting PostgreSQL service"
    sudo_run systemctl restart postgresql
    return
  fi

  fail "Could not restart PostgreSQL automatically."
}

print_result() {
  postgres_port="${POSTGRES_PORT:-5432}"

  log ""
  log "Done."
  log "Database: ${POSTGRES_DB}"
  log "PostgreSQL user: ${POSTGRES_USER}"
  log "Port: ${postgres_port}"
  log "Docker gateway for Directus: ${POSTGRES_DOCKER_GATEWAY}"
  log "Docker subnet allowed in pg_hba.conf: ${POSTGRES_DOCKER_SUBNET}"
  log ""
  log "Host DATABASE_URL:"
  log "postgresql+psycopg2://${POSTGRES_USER}:${POSTGRES_PASSWORD}@localhost:${postgres_port}/${POSTGRES_DB}"
  log ""
  log "Directus DB host from production containers:"
  log "${POSTGRES_DOCKER_GATEWAY}"
  log ""
  log "If UFW is enabled, allow ${POSTGRES_DOCKER_SUBNET} to reach tcp/${postgres_port}."
}

main() {
  load_env_file
  validate_required_vars
  validate_identifier "$POSTGRES_DB" "POSTGRES_DB"
  validate_identifier "$POSTGRES_USER" "POSTGRES_USER"
  ensure_psql_exists
  ensure_role
  ensure_database
  ensure_public_schema_access
  configure_postgresql_conf
  configure_pg_hba
  restart_postgres
  print_result
}

main "$@"
