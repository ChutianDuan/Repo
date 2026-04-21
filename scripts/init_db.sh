#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if [ -f .env ]; then
  set -a
  source ./.env
  set +a
fi

MYSQL_HOST="${MYSQL_HOST:-127.0.0.1}"
MYSQL_PORT="${MYSQL_PORT:-3306}"
MYSQL_DATABASE="${MYSQL_DATABASE:-ai_app}"
MYSQL_USER="${MYSQL_USER:-ai_user}"
MYSQL_PASSWORD="${MYSQL_PASSWORD:-ai_password}"
MYSQL_ADMIN_USER="${MYSQL_ADMIN_USER:-${MYSQL_USER}}"
MYSQL_ADMIN_PASSWORD="${MYSQL_ADMIN_PASSWORD:-${MYSQL_PASSWORD}}"

mysql_cmd() {
  local user="$1"
  local password="$2"
  shift 2

  local cmd=(
    mysql
    -h"${MYSQL_HOST}"
    -P"${MYSQL_PORT}"
    -u"${user}"
  )

  if [ -n "${password}" ]; then
    cmd+=("-p${password}")
  fi

  cmd+=("$@")
  "${cmd[@]}"
}

escape_identifier() {
  printf '%s' "$1" | sed 's/`/``/g'
}

escape_sql_string() {
  printf '%s' "$1" | sed "s/'/''/g"
}

DB_NAME_ESCAPED="$(escape_identifier "${MYSQL_DATABASE}")"
APP_USER_ESCAPED="$(escape_sql_string "${MYSQL_USER}")"
APP_PASSWORD_ESCAPED="$(escape_sql_string "${MYSQL_PASSWORD}")"

mysql_cmd "${MYSQL_ADMIN_USER}" "${MYSQL_ADMIN_PASSWORD}" <<SQL
CREATE DATABASE IF NOT EXISTS \`${DB_NAME_ESCAPED}\`
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;
SQL

if [ "${MYSQL_ADMIN_USER}" != "${MYSQL_USER}" ]; then
  mysql_cmd "${MYSQL_ADMIN_USER}" "${MYSQL_ADMIN_PASSWORD}" <<SQL
CREATE USER IF NOT EXISTS '${APP_USER_ESCAPED}'@'%' IDENTIFIED BY '${APP_PASSWORD_ESCAPED}';
GRANT ALL PRIVILEGES ON \`${DB_NAME_ESCAPED}\`.* TO '${APP_USER_ESCAPED}'@'%';
FLUSH PRIVILEGES;
SQL
fi

mysql_cmd "${MYSQL_USER}" "${MYSQL_PASSWORD}" "${MYSQL_DATABASE}" < db/init.sql

for migration in db/*_schema_upgrade.sql; do
  [ -f "${migration}" ] || continue
  mysql_cmd "${MYSQL_USER}" "${MYSQL_PASSWORD}" "${MYSQL_DATABASE}" < "${migration}"
done

mysql_cmd "${MYSQL_USER}" "${MYSQL_PASSWORD}" "${MYSQL_DATABASE}" -e "SHOW TABLES;"
