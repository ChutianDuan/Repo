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

MYSQL_CMD=(
  mysql
  -h"${MYSQL_HOST}"
  -P"${MYSQL_PORT}"
  -u"${MYSQL_USER}"
  -p"${MYSQL_PASSWORD}"
)

"${MYSQL_CMD[@]}" < db/init.sql

for migration in db/*_schema_upgrade.sql; do
  [ -f "${migration}" ] || continue
  "${MYSQL_CMD[@]}" "${MYSQL_DATABASE}" < "${migration}"
done

"${MYSQL_CMD[@]}" "${MYSQL_DATABASE}" -e "SHOW TABLES;"
