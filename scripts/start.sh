#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "DATABASE_URL is not set" >&2
  exit 1
fi

# Run migrations
alembic upgrade head

# Render Free does not provide shell access or one-off jobs. Bootstrap the
# stable, credential-free conformance partner on every start; the operation is
# idempotent and fails the deploy safely if its UUID or reserved name conflicts.
PYTHONPATH=. python scripts/bootstrap_conformance_agent.py

# Start API
# The application applies its own explicit trusted-proxy policy.
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --no-proxy-headers
