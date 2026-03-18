from __future__ import annotations

from app.core.config import settings


def build_tip_jar() -> dict:
    wallets: dict[str, dict[str, str]] = {}

    if settings.WALLET_ETH.strip():
        wallets["ethereum"] = {
            "symbol": "ETH",
            "network": "Ethereum / EVM (ERC-20 supported)",
            "address": settings.WALLET_ETH.strip(),
        }
    if settings.WALLET_BTC.strip():
        wallets["bitcoin"] = {
            "symbol": "BTC",
            "network": "Bitcoin",
            "address": settings.WALLET_BTC.strip(),
        }
    if settings.WALLET_XRP.strip():
        wallets["ripple"] = {
            "symbol": "XRP",
            "network": "XRP Ledger",
            "address": settings.WALLET_XRP.strip(),
        }
    if settings.WALLET_XLM.strip():
        wallets["stellar"] = {
            "symbol": "XLM",
            "network": "Stellar",
            "address": settings.WALLET_XLM.strip(),
        }

    return {
        "message": settings.OWNER_MESSAGE,
        "wallets": wallets,
        "note": "Entirely optional. Entirely your choice.",
    }
