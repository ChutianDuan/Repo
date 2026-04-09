#!/usr/bin/env bash
set -e

export PYTHONPATH=.
celery -A python_rag.modules.tasks.celery_app worker -l INFO