#!/bin/sh
set -e

case "$SERVICE_MODE" in
  api)
    exec uv run ./main.py
    ;;
  worker)
    exec uv run -m app.worker
    ;;
  *)
    echo "Unknown SERVICE_MODE: $SERVICE_MODE (expected 'api' or 'worker')"
    exit 1
    ;;
esac
