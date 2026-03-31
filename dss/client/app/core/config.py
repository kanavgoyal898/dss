"""
Purpose: DSS Peer Node configuration management via environment variables and defaults.
Responsibilities:
    - Declare all configurable parameters for the peer node process.
    - Load values from environment with sensible defaults.
    - Expose a singleton Settings instance consumed by all client modules.
Dependencies: pydantic-settings
"""

import os
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

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
    advertised_host: str = Field(default="127.0.0.1", validation_alias="DSS_ADVERTISED_HOST")
    chunk_size_bytes: int = Field(default=1024 * 1024, validation_alias="DSS_CHUNK_SIZE")
    capacity_bytes: int = Field(default=8 * 1024 * 1024 * 1024, validation_alias="DSS_CAPACITY")
    data_shards: int = Field(default=4, validation_alias="DSS_DATA_SHARDS")
    total_shards: int = Field(default=6, validation_alias="DSS_TOTAL_SHARDS")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def get_port(self) -> int:
        """Resolve port safely across environments."""
        return int(
            os.environ.get("PORT")
            or os.environ.get("DSS_NODE_PORT", self.port)
        )
    
    def get_advertised_host(self) -> str:
        """Resolve public host for this node."""
        if os.environ.get("DSS_ADVERTISED_HOST"):
            return os.environ["DSS_ADVERTISED_HOST"]

        render_url = os.environ.get("RENDER_EXTERNAL_URL")
        if render_url:
            return urlparse(render_url).hostname

        return self.advertised_host


@lru_cache()
def get_settings() -> Settings:
    """Return the cached singleton peer node Settings instance."""
    return Settings()
