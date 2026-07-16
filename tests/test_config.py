from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Settings


DATABASE_URL = "postgresql+asyncpg://sandbox:sandbox@localhost:5432/sandbox"


@pytest.mark.parametrize(
    "secret",
    [
        "",
        "short",
        "change-me-please-change-me-change-me",
        "generate-a-random-secret-at-least-32-characters",
    ],
)
def test_production_rejects_weak_or_placeholder_jwt_secrets(secret: str) -> None:
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        Settings(_env_file=None, ENV="production", DATABASE_URL=DATABASE_URL, JWT_SECRET=secret)


def test_production_accepts_strong_jwt_secret() -> None:
    settings = Settings(
        _env_file=None,
        ENV="production",
        DATABASE_URL=DATABASE_URL,
        JWT_SECRET="a-secure-random-looking-secret-that-is-long-enough",
    )

    assert settings.ENV == "production"


def test_development_allows_explicit_dev_secret() -> None:
    settings = Settings(
        _env_file=None,
        ENV="dev",
        DATABASE_URL=DATABASE_URL,
        JWT_SECRET="agent-sandbox-local-development-only-secret",
    )

    assert settings.JWT_SECRET.startswith("agent-sandbox-local")


def test_invalid_trusted_proxy_cidr_is_rejected() -> None:
    with pytest.raises(ValidationError, match="TRUSTED_PROXY_CIDRS"):
        Settings(
            _env_file=None,
            ENV="test",
            DATABASE_URL=DATABASE_URL,
            TRUSTED_PROXY_CIDRS="not-a-network",
        )
