from __future__ import annotations

import asyncio

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from starlette.middleware.trustedhost import TrustedHostMiddleware

import app.core.config as config_module
from app.core.config import Settings
from app.main import app


DATABASE_URL = "postgresql+asyncpg://sandbox:sandbox@localhost:5432/sandbox"


async def _request(
    target,
    method: str,
    path: str,
    *,
    headers: dict[str, str] | None = None,
    content: bytes | None = None,
    base_url: str = "http://testserver",
):
    transport = ASGITransport(app=target)
    async with AsyncClient(transport=transport, base_url=base_url) as client:
        return await client.request(method, path, headers=headers, content=content)


def test_security_headers_present_on_every_response() -> None:
    response = asyncio.run(_request(app, "GET", "/healthz"))

    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["cross-origin-opener-policy"] == "same-origin"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]


def test_oversized_request_body_is_rejected_before_handler() -> None:
    oversized = b"x" * (config_module.settings.MAX_REQUEST_BYTES + 1)

    response = asyncio.run(
        _request(
            app,
            "POST",
            "/register",
            content=oversized,
            headers={"content-type": "application/json"},
        )
    )

    assert response.status_code == 413
    # The rejection still carries the security headers.
    assert response.headers["x-content-type-options"] == "nosniff"


def test_body_within_limit_is_not_blocked_by_size_middleware() -> None:
    # A small body passes the size gate and reaches routing. An unrouted path is
    # used so the assertion proves the middleware let the request through (404)
    # without depending on the database.
    response = asyncio.run(
        _request(
            app,
            "POST",
            "/__no_such_route__",
            content=b'{"ok":true}',
            headers={"content-type": "application/json"},
        )
    )

    assert response.status_code != 413
    assert response.status_code == 404


def test_hsts_header_absent_when_disabled_and_present_when_enabled() -> None:
    disabled = asyncio.run(_request(app, "GET", "/healthz"))
    assert "strict-transport-security" not in disabled.headers

    original = config_module.settings.SECURITY_HSTS_SECONDS
    config_module.settings.SECURITY_HSTS_SECONDS = 63072000
    try:
        enabled = asyncio.run(_request(app, "GET", "/healthz"))
    finally:
        config_module.settings.SECURITY_HSTS_SECONDS = original

    assert enabled.headers["strict-transport-security"] == "max-age=63072000"


def test_allowed_hosts_list_appends_loopback_and_passes_wildcard() -> None:
    wildcard = Settings(_env_file=None, ENV="test", DATABASE_URL=DATABASE_URL, ALLOWED_HOSTS="*")
    assert wildcard.allowed_hosts_list == ["*"]

    restricted = Settings(
        _env_file=None,
        ENV="test",
        DATABASE_URL=DATABASE_URL,
        ALLOWED_HOSTS="sandbox.example, api.sandbox.example",
    )
    hosts = restricted.allowed_hosts_list
    assert "sandbox.example" in hosts
    assert "api.sandbox.example" in hosts
    # Loopback is always permitted so container/health probes are never blocked.
    assert "localhost" in hosts
    assert "127.0.0.1" in hosts


def _trusted_host_probe_app(allowed_hosts: list[str]) -> FastAPI:
    probe = FastAPI()

    @probe.get("/healthz")
    async def _healthz() -> dict[str, str]:
        return {"status": "ok"}

    probe.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)
    return probe


def test_trusted_host_rejects_unlisted_host() -> None:
    restricted = Settings(
        _env_file=None,
        ENV="test",
        DATABASE_URL=DATABASE_URL,
        ALLOWED_HOSTS="sandbox.example",
    )
    probe = _trusted_host_probe_app(restricted.allowed_hosts_list)

    good = asyncio.run(_request(probe, "GET", "/healthz", base_url="http://sandbox.example"))
    loopback = asyncio.run(_request(probe, "GET", "/healthz", base_url="http://localhost"))
    bad = asyncio.run(_request(probe, "GET", "/healthz", base_url="http://evil.example"))

    assert good.status_code == 200
    assert loopback.status_code == 200
    assert bad.status_code == 400
