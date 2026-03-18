from __future__ import annotations

from pydantic import BaseModel


class TipJar(BaseModel):
    message: str
    wallets: dict
    note: str
