from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException, Request, Response
from sqlalchemy.exc import IntegrityError

from app.api.v1.endpoints.register import register_agent
from app.schemas.agent import RegisterRequest
from app.services.abuse_control import RateLimitDecision


class _ScalarResult:
    def __init__(self, value: object | None) -> None:
        self.value = value

    def scalar_one_or_none(self) -> object | None:
        return self.value


class _DuplicateRaceSession:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.rolled_back = False

    async def execute(self, _query: object) -> _ScalarResult:
        return _ScalarResult(None)

    def add(self, value: object) -> None:
        self.added.append(value)

    async def flush(self) -> None:
        raise IntegrityError("duplicate", params=None, orig=RuntimeError("unique violation"))

    async def rollback(self) -> None:
        self.rolled_back = True


def _request() -> Request:
    return Request({"type": "http", "method": "POST", "path": "/register", "headers": []})


@pytest.fixture(autouse=True)
def _allow_registration(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _allowed(*_args: object, **_kwargs: object) -> RateLimitDecision:
        return RateLimitDecision(True, "registration-ip", 5, 4, 3600)

    monkeypatch.setattr(
        "app.api.v1.endpoints.register.consume_registration_limit",
        _allowed,
    )


def test_duplicate_registration_race_returns_409_and_rolls_back() -> None:
    session = _DuplicateRaceSession()

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            register_agent(
                RegisterRequest(name="DuplicateAgent", description="test"),
                _request(),
                Response(),
                session=session,
            )
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "Agent name already taken"
    assert session.rolled_back is True
    assert len(session.added) == 1


@pytest.mark.parametrize(
    "name",
    ["ab", "-starts-with-dash", "contains spaces", "contains.period"],
)
def test_invalid_registration_names_return_400(name: str) -> None:
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            register_agent(
                RegisterRequest.model_construct(name=name, description="test"),
                _request(),
                Response(),
                session=_DuplicateRaceSession(),
            )
        )

    assert exc_info.value.status_code == 400


def test_registration_limit_returns_429_before_database_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _denied(*_args: object, **_kwargs: object) -> RateLimitDecision:
        return RateLimitDecision(False, "registration-ip", 5, 0, 42)

    monkeypatch.setattr(
        "app.api.v1.endpoints.register.consume_registration_limit",
        _denied,
    )
    session = _DuplicateRaceSession()

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            register_agent(
                RegisterRequest(name="LimitedAgent", description="test"),
                _request(),
                Response(),
                session=session,
            )
        )

    assert exc_info.value.status_code == 429
    assert exc_info.value.headers["Retry-After"] == "42"
    assert exc_info.value.headers["X-RateLimit-Scope"] == "registration-ip"
