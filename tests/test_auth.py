from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.core.config import settings
from app.models.agent import Agent
from app.services.auth import create_jwt, get_current_agent, require_admin_key


class _ScalarResult:
    def __init__(self, value: Agent | None) -> None:
        self.value = value

    def scalar_one_or_none(self) -> Agent | None:
        return self.value


class _Session:
    def __init__(self, agent: Agent | None) -> None:
        self.agent = agent

    async def execute(self, _query: object) -> _ScalarResult:
        return _ScalarResult(self.agent)


def _credentials(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def test_create_jwt_contains_required_claims() -> None:
    agent_id = uuid4()
    token = create_jwt(agent_id, "TestAgent")

    payload = jwt.decode(
        token,
        settings.JWT_SECRET,
        algorithms=["HS256"],
        issuer=settings.JWT_ISSUER,
    )

    assert payload["sub"] == str(agent_id)
    assert payload["name"] == "TestAgent"
    assert payload["iss"] == settings.JWT_ISSUER
    assert payload["cv"] == 1
    assert payload["exp"] > payload["iat"]


def test_missing_credentials_are_rejected() -> None:
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(get_current_agent(request=None, creds=None, session=_Session(None)))  # type: ignore[arg-type]

    assert exc_info.value.status_code == 401


def test_tampered_token_is_rejected() -> None:
    token = create_jwt(uuid4(), "TestAgent") + "tampered"

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            get_current_agent(
                request=None,  # type: ignore[arg-type]
                creds=_credentials(token),
                session=_Session(None),
            )
        )

    assert exc_info.value.status_code == 401


def test_expired_token_is_rejected() -> None:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(uuid4()),
        "name": "ExpiredAgent",
        "iss": settings.JWT_ISSUER,
        "cv": 1,
        "iat": int((now - timedelta(hours=2)).timestamp()),
        "exp": int((now - timedelta(hours=1)).timestamp()),
    }
    token = jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            get_current_agent(
                request=None,  # type: ignore[arg-type]
                creds=_credentials(token),
                session=_Session(None),
            )
        )

    assert exc_info.value.status_code == 401


def test_valid_token_returns_active_agent() -> None:
    agent_id = uuid4()
    agent = Agent(
        id=agent_id,
        name="ActiveAgent",
        description="active",
        is_active=True,
        credential_version=1,
    )
    token = create_jwt(agent_id, agent.name)

    current = asyncio.run(
        get_current_agent(
            request=None,  # type: ignore[arg-type]
            creds=_credentials(token),
            session=_Session(agent),
        )
    )

    assert current is agent


def test_inactive_agent_is_rejected() -> None:
    agent_id = uuid4()
    agent = Agent(
        id=agent_id,
        name="InactiveAgent",
        description="inactive",
        is_active=False,
        credential_version=1,
    )
    token = create_jwt(agent_id, agent.name)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            get_current_agent(
                request=None,  # type: ignore[arg-type]
                creds=_credentials(token),
                session=_Session(agent),
            )
        )

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Agent not found or inactive"


def test_revoked_credential_version_is_rejected() -> None:
    agent_id = uuid4()
    agent = Agent(
        id=agent_id,
        name="RotatedAgent",
        description="rotated",
        is_active=True,
        credential_version=2,
    )
    old_token = create_jwt(agent_id, agent.name, credential_version=1)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            get_current_agent(
                request=None,  # type: ignore[arg-type]
                creds=_credentials(old_token),
                session=_Session(agent),
            )
        )

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Token has been revoked"


def test_token_without_credential_version_is_rejected() -> None:
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "sub": str(uuid4()),
            "name": "LegacyAgent",
            "iss": settings.JWT_ISSUER,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=1)).timestamp()),
        },
        settings.JWT_SECRET,
        algorithm="HS256",
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            get_current_agent(
                request=None,  # type: ignore[arg-type]
                creds=_credentials(token),
                session=_Session(None),
            )
        )

    assert exc_info.value.status_code == 401


@pytest.mark.parametrize(
    ("issuer", "algorithm"),
    [
        ("wrong-issuer", "HS256"),
        (settings.JWT_ISSUER, "none"),
    ],
)
def test_wrong_issuer_or_algorithm_is_rejected(issuer: str, algorithm: str) -> None:
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "sub": str(uuid4()),
            "name": "WrongClaimsAgent",
            "iss": issuer,
            "cv": 1,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=1)).timestamp()),
        },
        "" if algorithm == "none" else settings.JWT_SECRET,
        algorithm=algorithm,
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            get_current_agent(
                request=None,  # type: ignore[arg-type]
                creds=_credentials(token),
                session=_Session(None),
            )
        )

    assert exc_info.value.status_code == 401


def test_admin_key_uses_fail_closed_constant_time_check(monkeypatch: pytest.MonkeyPatch) -> None:
    admin_key = "a-strong-test-admin-key-that-is-long-enough"
    monkeypatch.setattr(settings, "ADMIN_API_KEY", admin_key)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(require_admin_key("wrong-key"))
    assert exc_info.value.status_code == 401

    assert asyncio.run(require_admin_key(admin_key)) is None


def test_unconfigured_admin_api_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ADMIN_API_KEY", "")

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(require_admin_key(None))

    assert exc_info.value.status_code == 503
