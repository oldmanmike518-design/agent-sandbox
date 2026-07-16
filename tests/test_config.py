from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Settings


DATABASE_URL = "postgresql+asyncpg://sandbox:sandbox@localhost:5432/sandbox"


def test_omitted_environment_fails_closed_with_development_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ENV")
    with pytest.raises(ValidationError):
        Settings(_env_file=None, DATABASE_URL=DATABASE_URL)


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
        JWT_EXPIRES_DAYS=30,
        ADMIN_API_KEY="a-separate-secure-admin-key-that-is-long-enough",
    )

    assert settings.ENV == "production"


def test_production_rejects_long_lived_tokens() -> None:
    with pytest.raises(ValidationError, match="JWT_EXPIRES_DAYS"):
        Settings(
            _env_file=None,
            ENV="production",
            DATABASE_URL=DATABASE_URL,
            JWT_SECRET="a-secure-random-looking-secret-that-is-long-enough",
            JWT_EXPIRES_DAYS=3650,
            ADMIN_API_KEY="a-separate-secure-admin-key-that-is-long-enough",
        )


def test_production_requires_strong_admin_key() -> None:
    with pytest.raises(ValidationError, match="ADMIN_API_KEY"):
        Settings(
            _env_file=None,
            ENV="production",
            DATABASE_URL=DATABASE_URL,
            JWT_SECRET="a-secure-random-looking-secret-that-is-long-enough",
            JWT_EXPIRES_DAYS=30,
            ADMIN_API_KEY="dev-only-admin-key",
        )


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
