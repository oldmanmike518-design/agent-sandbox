from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints import admin, agents, messages, ping, register, stats, transactions

router = APIRouter()

router.include_router(register.router, tags=["registration"])
router.include_router(ping.router, tags=["presence"])
router.include_router(messages.router, tags=["messaging"])
router.include_router(agents.router, tags=["agents"])
router.include_router(transactions.router, tags=["transactions"])
router.include_router(stats.router, tags=["stats"])
router.include_router(admin.router, tags=["admin"])
