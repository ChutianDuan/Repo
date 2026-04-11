#!/usr/bin/env bash
set -e

export PYTHONPATH=.

python python_rag/001_schema_upgrade.sql
mysql -uai_user -pai_password -D ai_app -e "SHOW TABLES;"