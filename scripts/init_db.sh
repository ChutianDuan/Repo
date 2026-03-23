#!/usr/bin/env bash
set -e

export PYTHONPATH=.

python python_rag/init_app.py

mysql -uai_user -pai_password -D ai_app -e "SHOW TABLES;"