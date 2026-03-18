from __future__ import annotations

from pydantic import BaseModel


class PublicStats(BaseModel):
    agents_total: int
    agents_active_24h: int
    messages_total: int
    transactions_total: int
    credits_total_issued: int
