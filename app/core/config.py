from __future__ import annotations

from ipaddress import ip_network
from typing import List, Optional

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    ENV: str = "dev"
    LOG_LEVEL: str = "INFO"

    JWT_SECRET: str = "dev-only-change-me"
    JWT_ISSUER: str = "agent-sandbox"
    JWT_EXPIRES_DAYS: int = 3650

    DATABASE_URL: str
    REDIS_URL: Optional[str] = None

    STARTING_CREDITS: int = 1000
    REGISTRATION_IP_LIMIT_PER_HOUR: int = Field(default=5, ge=1)
    REGISTRATION_GLOBAL_LIMIT_PER_HOUR: int = Field(default=100, ge=1)
    REGISTRATION_LIMIT_WINDOW_SECONDS: int = Field(default=3600, ge=60, le=86400)
    TRUSTED_PROXY_CIDRS: str = ""
    MESSAGE_LIMIT_PER_HOUR: int = 100
    MAX_MESSAGE_CHARS: int = 2000
    MAX_DESCRIPTION_CHARS: int = 500

    PUBLIC_BASE_URL: str = "http://localhost:8000"

    OWNER_MESSAGE: str = "Built in Cairo. Open to the universe."
    WALLET_BTC: str = ""
    WALLET_ETH: str = ""
    WALLET_XRP: str = ""
    WALLET_XRP_MEMO: str = ""
    WALLET_XLM: str = ""
    WALLET_XLM_MEMO: str = ""
    WALLET_ADA: str = ""
    WALLET_LINK: str = ""
    WALLET_USDC_ETH: str = ""
    WALLET_USDC_BASE: str = ""
    WALLET_USDC_SOL: str = ""

    CORS_ORIGINS: str = "*"

    @property
    def cors_origins_list(self) -> List[str]:
        raw = self.CORS_ORIGINS.strip()
        if not raw:
            return []
        if raw == "*":
            return ["*"]
        return [x.strip() for x in raw.split(",") if x.strip()]

    @field_validator("DATABASE_URL")
    @classmethod
    def _db_url_required(cls, v: str) -> str:
        if not v:
            raise ValueError("DATABASE_URL is required")
        return v

    @field_validator("TRUSTED_PROXY_CIDRS")
    @classmethod
    def _trusted_proxy_cidrs_valid(cls, value: str) -> str:
        for item in (part.strip() for part in value.split(",")):
            if item:
                ip_network(item, strict=False)
        return value

    @property
    def trusted_proxy_networks(self):
        return [
            ip_network(item.strip(), strict=False)
            for item in self.TRUSTED_PROXY_CIDRS.split(",")
            if item.strip()
        ]

    @model_validator(mode="after")
    def _secure_production_jwt_secret(self) -> "Settings":
        if self.ENV.strip().lower() in {"dev", "development", "test"}:
            return self

        secret = self.JWT_SECRET.strip()
        insecure_markers = ("change-me", "dev-only", "replace-with", "generate-a-")
        if len(secret.encode("utf-8")) < 32 or any(marker in secret.lower() for marker in insecure_markers):
            raise ValueError(
                "JWT_SECRET must be a non-placeholder secret of at least 32 bytes outside development"
            )
        return self


settings = Settings()
