"""
Purpose: DSS Coordinator configuration management via environment variables and defaults.
Responsibilities:
    - Declare all configurable parameters for the coordinator process.
    - Load values from environment with sensible defaults for development.
    - Expose a singleton Settings instance consumed by all server modules.
Dependencies: pydantic-settings
"""

from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """DSS Coordinator runtime configuration."""

    app_name: str = "DSS Coordinator"
    host: str = Field(default="0.0.0.0", validation_alias="DSS_SERVER_HOST")
    port: int = Field(default=8000, validation_alias="DSS_SERVER_PORT")
    jwt_secret: str = Field(default="dss-change-me-in-production", validation_alias="DSS_JWT_SECRET")
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = Field(default=60, validation_alias="DSS_JWT_EXPIRE_MINUTES")

    admin_password: str = Field(default="", validation_alias="DSS_ADMIN_PASSWORD")

    network_mode: str = Field(default="global", validation_alias="DSS_NETWORK_MODE")
    allowed_ips: List[str] = Field(default=[], validation_alias="DSS_ALLOWED_IPS")

    peer_heartbeat_timeout_seconds: int = Field(default=30, validation_alias="DSS_HEARTBEAT_TIMEOUT")
    health_check_interval_seconds: int = Field(default=15, validation_alias="DSS_HEALTH_INTERVAL")

    data_shards: int = Field(default=4, validation_alias="DSS_DATA_SHARDS")
    total_shards: int = Field(default=6, validation_alias="DSS_TOTAL_SHARDS")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    """Return the cached singleton Settings instance."""
    return Settings()
