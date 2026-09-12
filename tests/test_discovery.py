from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from httpx import ASGITransport, AsyncClient

from app.core.discovery import (
    build_agent_manifest,
    build_llms_txt,
    build_sitemap_xml,
)
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
    # Policies are advertised for discovery.
    assert "privacy" in body["policies"]
    assert "acceptable_use" in body["policies"]


def test_discovery_surface_advertises_verification() -> None:
    """The verification core is the product; discovery must say so.

    The service shipped verification while every discovery artifact still
    described the older messaging sandbox, so agents could not find the feature
    they came for.
    """
    manifest = build_agent_manifest()
    llms = build_llms_txt()

    verification = manifest["verification"]
    assert verification["profile"] == "rest-interop"
    assert len(verification["scored_checks"]) == 8
    assert "FAIL" in verification["result_states"]

    capability_ids = {cap["id"] for cap in manifest["capabilities"]}
    assert {"open_verification", "finalize_verification", "badge"} <= capability_ids

    assert "/verify" in llms
    assert "badge.json" in llms
    # Wording discipline from the Interop Spec: the claim is always the weaker one.
    assert "never" in manifest["verification"]["neutrality"].lower()
    assert "certified" not in manifest["description"].lower()


def test_robots_txt_opens_the_site_and_points_at_the_sitemap() -> None:
    response = asyncio.run(_get("/robots.txt"))

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "Allow: /" in response.text
    assert "Sitemap: " in response.text
    assert "/llms.txt" in response.text
    # Admin surfaces and metrics are never crawl targets.
    assert "Disallow: /admin/" in response.text
    assert "Disallow: /metrics" in response.text


def test_sitemap_lists_public_pages_and_no_unlisted_reports() -> None:
    xml = build_sitemap_xml()

    assert xml.startswith('<?xml version="1.0" encoding="UTF-8"?>')
    assert "/reports</loc>" in xml
    assert "<lastmod>" not in xml

    dated = datetime(2026, 7, 19, tzinfo=timezone.utc)
    with_reports = build_sitemap_xml([("eR1129MH5RLwvAdl", dated), ("noDate", None)])

    assert "/reports/eR1129MH5RLwvAdl</loc><lastmod>2026-07-19</lastmod>" in with_reports
    assert "/reports/noDate</loc></url>" in with_reports


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
