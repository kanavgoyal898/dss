"""
Purpose: DSS Peer Node configuration management via environment variables and defaults.
Responsibilities:
    - Declare all configurable parameters for the peer node process.
    - Load values from environment with sensible defaults.
    - Expose a singleton Settings instance consumed by all client modules.
Dependencies: pydantic-settings
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """DSS Peer Node runtime configuration."""

    app_name: str = "DSS Node"
    host: str = Field(default="0.0.0.0", validation_alias="DSS_NODE_HOST")
    port: int = Field(default=8100, validation_alias="DSS_NODE_PORT")

    coordinator_url: str = Field(
        default="http://localhost:8000", validation_alias="DSS_COORDINATOR_URL"
    )

    identity_dir: Path = Field(
        default=Path.home() / ".dss" / "identity", validation_alias="DSS_IDENTITY_DIR"
    )
    storage_dir: Path = Field(
        default=Path.home() / ".dss" / "shards", validation_alias="DSS_STORAGE_DIR"
    )

    heartbeat_interval_seconds: int = Field(default=15, validation_alias="DSS_HEARTBEAT_INTERVAL")
    chunk_size_bytes: int = Field(default=1024 * 1024, validation_alias="DSS_CHUNK_SIZE")
    advertised_host: str = Field(default="127.0.0.1", validation_alias="DSS_ADVERTISED_HOST")
    capacity_bytes: int = Field(default=10 * 1024 * 1024 * 1024, validation_alias="DSS_CAPACITY")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    """Return the cached singleton peer node Settings instance."""
    return Settings()
