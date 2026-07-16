from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_session
from app.models.agent import Agent

bearer_scheme = HTTPBearer(auto_error=False)
admin_key_scheme = APIKeyHeader(name="X-Admin-Key", auto_error=False)


def create_jwt(agent_id: UUID, agent_name: str, credential_version: int = 1) -> str:
    now = datetime.now(timezone.utc)
    exp = now + timedelta(days=settings.JWT_EXPIRES_DAYS)
    payload = {
        "sub": str(agent_id),
        "name": agent_name,
        "iss": settings.JWT_ISSUER,
        "cv": credential_version,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


def _unauthorized(detail: str = "Invalid or missing token") -> HTTPException:
    return HTTPException(status_code=401, detail=detail)


async def require_admin_key(
    api_key: str | None = Depends(admin_key_scheme),
) -> None:
    configured_key = settings.ADMIN_API_KEY
    if not configured_key:
        raise HTTPException(status_code=503, detail="Admin API is not configured")
    if api_key is None or not secrets.compare_digest(api_key, configured_key):
        raise _unauthorized()


async def get_current_agent(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_session),
) -> Agent:
    if creds is None or not creds.credentials:
        raise _unauthorized()

    token = creds.credentials
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=["HS256"],
            options={"require": ["exp", "iat", "iss", "sub", "cv"]},
            issuer=settings.JWT_ISSUER,
        )
        agent_id = UUID(payload["sub"])
        credential_version = payload["cv"]
        if not isinstance(credential_version, int) or isinstance(credential_version, bool):
            raise ValueError("Invalid credential version")
    except Exception:
        raise _unauthorized()

    result = await session.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if agent is None or not agent.is_active:
        raise _unauthorized("Agent not found or inactive")
    if agent.credential_version != credential_version:
        raise _unauthorized("Token has been revoked")

    return agent
