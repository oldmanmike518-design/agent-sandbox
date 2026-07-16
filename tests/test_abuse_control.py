from __future__ import annotations

from fastapi import Request

from app.core.config import settings
from app.services.abuse_control import RegistrationLimitDecision, get_client_ip


def _request(peer: str, forwarded_for: str | None = None) -> Request:
    headers = []
    if forwarded_for is not None:
        headers.append((b"x-forwarded-for", forwarded_for.encode("ascii")))
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/register",
            "headers": headers,
            "client": (peer, 12345),
        }
    )


def test_untrusted_peer_cannot_spoof_forwarded_for(monkeypatch) -> None:
    monkeypatch.setattr(settings, "TRUSTED_PROXY_CIDRS", "10.0.0.0/8")

    assert get_client_ip(_request("203.0.113.10", "198.51.100.7")) == "203.0.113.10"


def test_trusted_proxy_chain_uses_nearest_untrusted_client(monkeypatch) -> None:
    monkeypatch.setattr(settings, "TRUSTED_PROXY_CIDRS", "10.0.0.0/8,192.0.2.0/24")

    assert (
        get_client_ip(
            _request(
                "10.0.0.9",
                "198.51.100.7, 203.0.113.8, 192.0.2.4",
            )
        )
        == "203.0.113.8"
    )


def test_denied_registration_decision_includes_retry_after() -> None:
    decision = RegistrationLimitDecision(False, "registration-global", 100, 0, 17)

    assert decision.headers["Retry-After"] == "17"
    assert decision.headers["X-RateLimit-Remaining"] == "0"
