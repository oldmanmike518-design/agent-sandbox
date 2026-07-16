#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "DATABASE_URL is not set" >&2
  exit 1
fi

# Run migrations
alembic upgrade head

# Start API
# The application applies its own explicit trusted-proxy policy.
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --no-proxy-headers
