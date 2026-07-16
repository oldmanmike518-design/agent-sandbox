from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_healthz_is_reachable() -> None:
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_tip_jar_is_reachable_by_get_and_post() -> None:
    get_response = client.get("/transaction/tip")
    post_response = client.post("/transaction/tip")

    assert get_response.status_code == 200
    assert post_response.status_code == 200
    assert get_response.json() == post_response.json()
    assert "wallets" in get_response.json()


def test_root_links_to_configured_docs() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "http://localhost:8000/docs" in response.text
    assert "http://localhost:8000/stats" in response.text
