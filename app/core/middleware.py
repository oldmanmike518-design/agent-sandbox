from __future__ import annotations

from starlette.datastructures import Headers
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.config import settings


# Static response headers applied to every response. The Content-Security-Policy
# is deliberately narrow: it blocks framing/clickjacking and base-tag/plugin
# abuse without restricting script/style sources, so the intentionally public
# Swagger UI and ReDoc (which load assets from a CDN) keep working.
_STATIC_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Content-Security-Policy": "frame-ancestors 'none'; base-uri 'none'; object-src 'none'",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach standard hardening headers to every response."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        response = await call_next(request)
        for key, value in _STATIC_SECURITY_HEADERS.items():
            response.headers.setdefault(key, value)

        hsts_seconds = settings.SECURITY_HSTS_SECONDS
        if hsts_seconds > 0:
            # Browsers only honour HSTS over HTTPS and ignore it over plain HTTP,
            # so it is safe to set unconditionally when explicitly enabled.
            response.headers.setdefault(
                "Strict-Transport-Security", f"max-age={hsts_seconds}"
            )
        return response


class VerifierIncidentMiddleware(BaseHTTPMiddleware):
    """Best-effort capture of verifier 5xx responses during active runs."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        try:
            response = await call_next(request)
        except Exception:
            try:
                await _record_verifier_incident(request, 500)
            except Exception:  # noqa: BLE001
                pass
            raise
        if response.status_code >= 500:
            try:
                await _record_verifier_incident(
                    request, response.status_code
                )
            except Exception:  # noqa: BLE001
                pass
        return response


async def _record_verifier_incident(
    request: Request, status_code: int
) -> None:
    from uuid import UUID

    import jwt
    from sqlalchemy.orm.attributes import flag_modified

    from app.db.session import AsyncSessionLocal
    from app.services.verification.observations import get_active_run
    from app.utils.time import utc_now

    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        return
    payload = jwt.decode(
        auth[7:],
        settings.JWT_SECRET,
        algorithms=["HS256"],
        options={"require": ["sub"]},
        issuer=settings.JWT_ISSUER,
    )
    agent_id = UUID(payload["sub"])
    async with AsyncSessionLocal() as session:
        run = await get_active_run(session, agent_id)
        if run is None:
            return
        run.verifier_incidents = [
            *run.verifier_incidents,
            {
                "path": request.url.path,
                "status": status_code,
                "at": utc_now().isoformat(),
            },
        ]
        run.verifier_fault = True
        flag_modified(run, "verifier_incidents")
        await session.commit()


class MaxBodySizeMiddleware:
    """Reject requests whose declared body exceeds the configured cap.

    This inspects the ``Content-Length`` header, which every standard HTTP
    client (curl, httpx, browsers) sends when a request carries a body. It is a
    defense-in-depth layer on top of the per-field Pydantic size limits; it does
    not attempt to bound chunked requests that omit ``Content-Length``, which the
    schema field limits already constrain in practice.
    """

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        content_length = Headers(scope=scope).get("content-length")
        if content_length is not None:
            try:
                declared = int(content_length)
            except ValueError:
                await PlainTextResponse(
                    "Invalid Content-Length", status_code=400
                )(scope, receive, send)
                return
            if declared > self.max_bytes:
                await PlainTextResponse(
                    "Request body too large", status_code=413
                )(scope, receive, send)
                return

        await self.app(scope, receive, send)
