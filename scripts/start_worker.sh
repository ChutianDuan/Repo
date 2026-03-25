#!/usr/bin/env bash
set -e

export PYTHONPATH=.
celery -A python_rag.workers.celery_app.celery_app worker -l INFO