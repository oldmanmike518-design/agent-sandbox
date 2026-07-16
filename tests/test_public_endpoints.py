from __future__ import annotations

import asyncio

from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.db.session import get_session
from app.main import app
from app.services.readiness import expected_schema_revision


async def _request(method: str, path: str, *, headers: dict[str, str] | None = None):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.request(method, path, headers=headers)


class _RevisionResult:
    def __init__(self, revision: str | None) -> None:
        self.revision = revision

    def scalar_one_or_none(self) -> str | None:
        return self.revision


class _ReadinessSession:
    def __init__(self, revision: str | None = None, *, unavailable: bool = False) -> None:
        self.revision = revision
        self.unavailable = unavailable

    async def execute(self, _query: object) -> _RevisionResult:
        if self.unavailable:
            raise OSError("database unavailable")
        return _RevisionResult(self.revision)


async def _override_session(session: _ReadinessSession):
    yield session


def _readiness_request(session: _ReadinessSession):
    async def _override():
        async for value in _override_session(session):
            yield value

    app.dependency_overrides[get_session] = _override
    try:
        return asyncio.run(_request("GET", "/readyz"))
    finally:
        app.dependency_overrides.pop(get_session, None)


def test_healthz_is_reachable() -> None:
    response = asyncio.run(_request("GET", "/healthz"))

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readyz_requires_database_and_current_migration() -> None:
    response = _readiness_request(
        _ReadinessSession(revision=expected_schema_revision())
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "database": "available",
        "schema": "current",
    }


def test_readyz_rejects_schema_mismatch_and_database_failure() -> None:
    mismatch = _readiness_request(_ReadinessSession(revision="old-revision"))
    unavailable = _readiness_request(_ReadinessSession(unavailable=True))

    assert mismatch.status_code == 503
    assert mismatch.json() == {
        "status": "not_ready",
        "database": "available",
        "schema": "mismatch",
    }
    assert unavailable.status_code == 503
    assert unavailable.json() == {
        "status": "not_ready",
        "database": "unavailable",
        "schema": "unknown",
    }


def test_metrics_requires_dedicated_bearer_key() -> None:
    missing = asyncio.run(_request("GET", "/metrics"))
    wrong = asyncio.run(
        _request(
            "GET",
            "/metrics",
            headers={"Authorization": "Bearer wrong-key"},
        )
    )
    allowed = asyncio.run(
        _request(
            "GET",
            "/metrics",
            headers={"Authorization": f"Bearer {settings.METRICS_API_KEY}"},
        )
    )

    assert missing.status_code == 401
    assert missing.headers["WWW-Authenticate"] == "Bearer"
    assert wrong.status_code == 401
    assert allowed.status_code == 200
    assert "http_requests_total" in allowed.text


def test_tip_jar_is_reachable_by_get_and_post() -> None:
    get_response = asyncio.run(_request("GET", "/transaction/tip"))
    post_response = asyncio.run(_request("POST", "/transaction/tip"))

    assert get_response.status_code == 200
    assert post_response.status_code == 200
    assert get_response.json() == post_response.json()
    assert "wallets" in get_response.json()


def test_root_links_to_configured_docs() -> None:
    response = asyncio.run(_request("GET", "/"))

    assert response.status_code == 200
    assert "http://localhost:8000/docs" in response.text
    assert "http://localhost:8000/stats" in response.text
