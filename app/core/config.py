from __future__ import annotations

from ipaddress import ip_network
from typing import List, Optional

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    ENV: str = "production"
    LOG_LEVEL: str = "INFO"

    JWT_SECRET: str = "dev-only-change-me"
    JWT_ISSUER: str = "agent-sandbox"
    JWT_EXPIRES_DAYS: int = Field(default=3650, ge=1)
    ADMIN_API_KEY: str = "dev-only-admin-key"
    METRICS_API_KEY: str = "dev-only-metrics-key"

    DATABASE_URL: str
    REDIS_URL: Optional[str] = None

    STARTING_CREDITS: int = 1000
    REGISTRATION_IP_LIMIT_PER_HOUR: int = Field(default=5, ge=1)
    REGISTRATION_GLOBAL_LIMIT_PER_HOUR: int = Field(default=100, ge=1)
    REGISTRATION_LIMIT_WINDOW_SECONDS: int = Field(default=3600, ge=60, le=86400)
    RATE_LIMIT_BUCKET_RETENTION_SECONDS: int = Field(default=86400, ge=0, le=604800)
    WRITE_IP_LIMIT_PER_MINUTE: int = Field(default=60, ge=1)
    WRITE_GLOBAL_LIMIT_PER_MINUTE: int = Field(default=600, ge=1)
    WRITE_LIMIT_WINDOW_SECONDS: int = Field(default=60, ge=10, le=3600)
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

    # Host header allowlist (comma-separated). "*" allows any host. When a
    # specific list is set, loopback hosts are always appended so container and
    # local health probes are never rejected.
    ALLOWED_HOSTS: str = "*"

    # Maximum accepted request body size in bytes (declared Content-Length).
    MAX_REQUEST_BYTES: int = Field(default=65536, ge=1024, le=10_485_760)

    # Strict-Transport-Security max-age in seconds. 0 disables the header;
    # enable it only on a dedicated custom domain served over HTTPS.
    SECURITY_HSTS_SECONDS: int = Field(default=0, ge=0, le=63072000)

    @property
    def cors_origins_list(self) -> List[str]:
        raw = self.CORS_ORIGINS.strip()
        if not raw:
            return []
        if raw == "*":
            return ["*"]
        return [x.strip() for x in raw.split(",") if x.strip()]

    @property
    def allowed_hosts_list(self) -> List[str]:
        raw = self.ALLOWED_HOSTS.strip()
        if not raw or raw == "*":
            return ["*"]
        hosts = [h.strip() for h in raw.split(",") if h.strip()]
        for loopback in ("localhost", "127.0.0.1"):
            if loopback not in hosts:
                hosts.append(loopback)
        return hosts

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
        if self.JWT_EXPIRES_DAYS > 90:
            raise ValueError("JWT_EXPIRES_DAYS must be 90 or fewer outside development")

        admin_key = self.ADMIN_API_KEY.strip()
        if len(admin_key.encode("utf-8")) < 32 or any(
            marker in admin_key.lower() for marker in insecure_markers
        ):
            raise ValueError(
                "ADMIN_API_KEY must be a non-placeholder secret of at least 32 bytes outside development"
            )

        metrics_key = self.METRICS_API_KEY.strip()
        if len(metrics_key.encode("utf-8")) < 32 or any(
            marker in metrics_key.lower() for marker in insecure_markers
        ):
            raise ValueError(
                "METRICS_API_KEY must be a non-placeholder secret of at least 32 bytes outside development"
            )
        if len({secret, admin_key, metrics_key}) != 3:
            raise ValueError(
                "JWT_SECRET, ADMIN_API_KEY, and METRICS_API_KEY must be distinct outside development"
            )
        return self


settings = Settings()
