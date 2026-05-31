#!/bin/bash
set -a
source "$(dirname "$0")/.env"
set +a

exec "$(dirname "$0")/.venv/bin/uvicorn" server:app --host 0.0.0.0 --port 8000
