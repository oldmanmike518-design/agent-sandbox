from __future__ import annotations

import os


os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://sandbox:sandbox@localhost:5432/sandbox",
)
os.environ.setdefault("JWT_SECRET", "agent-sandbox-local-development-only-secret")
