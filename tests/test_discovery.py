from __future__ import annotations

import asyncio

from httpx import ASGITransport, AsyncClient

from app.core.discovery import build_agent_manifest, build_llms_txt
from app.main import app


async def _get(path: str):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.get(path)


def test_llms_txt_is_served_as_plain_text() -> None:
    response = asyncio.run(_get("/llms.txt"))

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "# Agent Sandbox" in response.text
    assert "/register" in response.text
    assert "/.well-known/agent-manifest.json" in response.text


def test_agent_manifest_is_served_as_json() -> None:
    response = asyncio.run(_get("/.well-known/agent-manifest.json"))

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Agent Sandbox"
    assert body["authentication"]["type"] == "http_bearer_jwt"
    # Credits must be advertised as non-monetary.
    assert body["credits"]["monetary"] is False
    assert body["credits"]["convertible"] is False
    capability_ids = {cap["id"] for cap in body["capabilities"]}
    assert {"register", "send_message", "send_credits", "stats"} <= capability_ids


def test_manifest_and_llms_use_configured_base_url() -> None:
    manifest = build_agent_manifest()
    llms = build_llms_txt()
    base = manifest["base_url"]

    assert manifest["openapi_url"] == f"{base}/openapi.json"
    assert base in llms


def test_openapi_schema_exposes_core_paths() -> None:
    schema = app.openapi()

    assert schema["openapi"].startswith("3.")
    for path in ("/register", "/message/send", "/transaction/send", "/agents", "/stats"):
        assert path in schema["paths"]
