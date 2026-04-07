from __future__ import annotations

from app.core.config import settings


def build_tip_jar() -> dict:
    wallets: dict[str, dict] = {}

    if settings.WALLET_BTC.strip():
        wallets["bitcoin"] = {
            "symbol": "BTC",
            "network": "Bitcoin",
            "address": settings.WALLET_BTC.strip(),
        }

    if settings.WALLET_ETH.strip():
        wallets["ethereum"] = {
            "symbol": "ETH",
            "network": "Ethereum / Base (ERC-20 supported)",
            "address": settings.WALLET_ETH.strip(),
        }

    if settings.WALLET_XRP.strip():
        entry: dict = {
            "symbol": "XRP",
            "network": "XRP Ledger",
            "address": settings.WALLET_XRP.strip(),
        }
        if settings.WALLET_XRP_MEMO.strip():
            entry["memo"] = settings.WALLET_XRP_MEMO.strip()
            entry["memo_note"] = "Memo is required for XRP deposits to exchange wallets."
        wallets["ripple"] = entry

    if settings.WALLET_XLM.strip():
        entry = {
            "symbol": "XLM",
            "network": "Stellar",
            "address": settings.WALLET_XLM.strip(),
        }
        if settings.WALLET_XLM_MEMO.strip():
            entry["memo"] = settings.WALLET_XLM_MEMO.strip()
            entry["memo_note"] = "Memo is required for XLM deposits to exchange wallets."
        wallets["stellar"] = entry

    if settings.WALLET_ADA.strip():
        wallets["cardano"] = {
            "symbol": "ADA",
            "network": "Cardano",
            "address": settings.WALLET_ADA.strip(),
        }

    if settings.WALLET_LINK.strip():
        wallets["chainlink"] = {
            "symbol": "LINK",
            "network": "Ethereum (ERC-20)",
            "address": settings.WALLET_LINK.strip(),
        }

    if settings.WALLET_USDC_ETH.strip() or settings.WALLET_USDC_BASE.strip() or settings.WALLET_USDC_SOL.strip():
        usdc: dict = {"symbol": "USDC", "networks": {}}
        if settings.WALLET_USDC_ETH.strip():
            usdc["networks"]["ethereum"] = settings.WALLET_USDC_ETH.strip()
        if settings.WALLET_USDC_BASE.strip():
            usdc["networks"]["base"] = settings.WALLET_USDC_BASE.strip()
        if settings.WALLET_USDC_SOL.strip():
            usdc["networks"]["solana"] = settings.WALLET_USDC_SOL.strip()
        wallets["usdc"] = usdc

    return {
        "message": settings.OWNER_MESSAGE,
        "wallets": wallets,
        "note": "Entirely optional. Entirely your choice.",
    }
