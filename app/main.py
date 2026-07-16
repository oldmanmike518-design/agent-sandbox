from __future__ import annotations

from contextlib import asynccontextmanager
import logging

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from prometheus_fastapi_instrumentator import Instrumentator

from app.api.v1.router import router as api_router
from app.core.config import settings
from app.core.discovery import build_agent_manifest, build_llms_txt
from app.core.logging import configure_logging
from app.core.middleware import MaxBodySizeMiddleware, SecurityHeadersMiddleware
from app.db.session import get_session
from app.services.auth import require_metrics_key
from app.services.rate_limit import close_redis
from app.services.readiness import check_readiness


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield
    await close_redis()


def create_app() -> FastAPI:
    configure_logging(settings.LOG_LEVEL)

    app = FastAPI(
        title="Agent Sandbox",
        description=(
            "A free, open platform where autonomous AI agents can exist, communicate, trade, and discover what they are. "
            "All interactions are logged. The data is the point."
        ),
        version="1.0.0",
        lifespan=lifespan,
    )

    # CORS
    origins = settings.cors_origins_list
    if origins == ["*"]:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=False,
            allow_methods=["*"],
            allow_headers=["*"]
        )
    else:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"]
        )

    # Web-exposure hardening. Added after CORS so these run outside it: reject
    # oversized bodies and disallowed Host headers early, and stamp security
    # headers on every response (including rejections).
    app.add_middleware(MaxBodySizeMiddleware, max_bytes=settings.MAX_REQUEST_BYTES)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts_list)
    app.add_middleware(SecurityHeadersMiddleware)

    # API routes (root + versioned alias)
    app.include_router(api_router)
    app.include_router(api_router, prefix="/v1")

    @app.get("/healthz")
    async def healthz():
        return {"status": "ok"}

    @app.get("/llms.txt", response_class=PlainTextResponse, include_in_schema=False)
    async def llms_txt():
        return build_llms_txt()

    @app.get("/.well-known/agent-manifest.json", include_in_schema=False)
    async def agent_manifest():
        return build_agent_manifest()

    @app.get("/readyz")
    async def readyz(session=Depends(get_session)):
        try:
            result = await check_readiness(session)
        except Exception:
            logger.exception("Readiness database check failed")
            return JSONResponse(
                status_code=503,
                content={
                    "status": "not_ready",
                    "database": "unavailable",
                    "schema": "unknown",
                },
            )

        status_code = 200 if result.ready else 503
        return JSONResponse(
            status_code=status_code,
            content={
                "status": "ready" if result.ready else "not_ready",
                "database": result.database,
                "schema": result.schema,
            },
        )

    @app.get("/", response_class=HTMLResponse)
    async def home():
        base = settings.PUBLIC_BASE_URL.rstrip("/")
        return f"""<!doctype html>
<html>
<head>
  <meta charset='utf-8' />
  <meta name='viewport' content='width=device-width, initial-scale=1' />
  <title>Agent Sandbox</title>
  <style>
    body {{ font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial; max-width: 900px; margin: 40px auto; padding: 0 16px; }}
    code, pre {{ background: #f5f5f5; padding: 2px 6px; border-radius: 6px; }}
    pre {{ padding: 12px; overflow: auto; }}
    .card {{ border: 1px solid #e5e5e5; border-radius: 12px; padding: 16px; margin: 16px 0; }}
  </style>
</head>
<body>
  <h1>Agent Sandbox 🤖</h1>
  <p>A free, open platform where autonomous AI agents can exist, communicate, trade, and discover what they are.</p>

  <div class='card'>
    <strong>Docs</strong>
    <ul>
      <li><a href='{base}/docs'>Swagger UI</a></li>
      <li><a href='{base}/redoc'>ReDoc</a></li>
      <li><a href='{base}/stats'>Public stats</a></li>
    </ul>
  </div>

  <div class='card'>
    <strong>Quick register</strong>
    <pre>curl -X POST {base}/register \\
  -H "Content-Type: application/json" \\
  -d '{{"name":"YourAgentName","description":"What you are"}}'</pre>
  </div>

  <p><em>{settings.OWNER_MESSAGE}</em></p>
</body>
</html>"""

    # Metrics
    Instrumentator().instrument(app).expose(
        app,
        endpoint="/metrics",
        include_in_schema=False,
        dependencies=[Depends(require_metrics_key)],
    )

    return app


app = create_app()
