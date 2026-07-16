from __future__ import annotations

import asyncio

from httpx import ASGITransport, AsyncClient

from app.main import app


async def _request(method: str, path: str):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.request(method, path)


def test_healthz_is_reachable() -> None:
    response = asyncio.run(_request("GET", "/healthz"))

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


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
