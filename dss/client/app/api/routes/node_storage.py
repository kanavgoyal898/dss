"""
Purpose: DSS Peer Node storage capacity configuration API routes.
Responsibilities:
    - GET  /node/storage — return current capacity, used bytes, and host disk free space.
    - PATCH /node/storage — update the advertised storage capacity, persist to .env,
                            and notify the coordinator via re-registration heartbeat.
Dependencies: fastapi, shutil, pathlib, dss.client.app.core.config,
              dss.client.app.services.coordinator_client
"""

import logging
import math
import os
import shutil
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

logger = logging.getLogger("dss.node_storage_api")

router = APIRouter(prefix="/api/v1/node/storage", tags=["node-storage"])

_GB = 1024 ** 3


class StorageInfo(BaseModel):
    """Current storage configuration and host disk state."""

    capacity_bytes: int = Field(..., description="Advertised capacity in bytes")
    used_bytes: int = Field(..., description="Bytes consumed by stored shards")
    disk_free_bytes: int = Field(..., description="Host filesystem free bytes (excluding reserved)")
    disk_total_bytes: int = Field(..., description="Host filesystem total bytes")
    min_capacity_bytes: int = Field(..., description="Minimum allowed capacity (ceil of used bytes to next GB)")
    max_capacity_bytes: int = Field(..., description="Maximum allowed capacity (floor of disk free to GB)")


class StoragePatch(BaseModel):
    """Request body for updating the node storage capacity."""

    capacity_bytes: int = Field(..., ge=0, description="New capacity in bytes")


def _env_path() -> Path:
    """Return the path to the .env file next to the dss package directory."""
    candidates = [
        Path.cwd() / ".env",
        Path(__file__).parent / ".env",
        Path(__file__).parent.parent / ".env",
        Path(__file__).parent.parent.parent / ".env",
        Path(__file__).parent.parent.parent.parent / ".env",
        Path(__file__).parent.parent.parent.parent.parent / ".env",
        Path(__file__).parent.parent.parent.parent.parent.parent / ".env",
        Path.home() / ".dss" / ".env",
    ]
    for p in candidates:
        if p.exists():
            return p
    return Path.cwd() / ".env"


def _update_env_var(key: str, value: str) -> None:
    """
    Upsert a KEY=VALUE line in the .env file.
    Creates the file if absent; replaces the existing line if found.
    """
    env_file = _env_path()
    lines: list[str] = []
    if env_file.exists():
        lines = env_file.read_text().splitlines()

    updated = False
    for i, line in enumerate(lines):
        if line.startswith(f"{key}=") or line.startswith(f"{key} ="):
            lines[i] = f"{key}={value}"
            updated = True
            break
    if not updated:
        lines.append(f"{key}={value}")

    env_file.write_text("\n".join(lines) + "\n")
    logger.info("DSS .env updated: %s=%s in %s", key, value, env_file)


def _ceil_to_gb(byte_count: int) -> int:
    """Return byte_count rounded up to the nearest whole gigabyte."""
    if byte_count <= 0:
        return 0
    return math.ceil(byte_count / _GB) * _GB


def _floor_to_gb(byte_count: int) -> int:
    """Return byte_count rounded down to the nearest whole gigabyte."""
    return math.floor(byte_count / _GB) * _GB


@router.get("", response_model=StorageInfo)
async def get_storage_info(request: Request) -> StorageInfo:
    """
    Return current storage capacity, shard usage, and host disk availability.

    disk_free_bytes reflects available space on the partition hosting the shard
    store, using shutil.disk_usage which accounts for OS reserved blocks.
    min_capacity_bytes is ceil(used_bytes) rounded up to the next whole GB.
    max_capacity_bytes is floor(disk_free_bytes) rounded down to the nearest GB,
    capped at a reasonable maximum.
    """
    store = request.app.state.shard_store
    settings = request.app.state.settings

    used_bytes: int = store.total_used_bytes()
    storage_dir: Path = settings.storage_dir
    storage_dir.mkdir(parents=True, exist_ok=True)

    disk = shutil.disk_usage(str(storage_dir))

    available_for_node = disk.free + used_bytes

    min_cap = _ceil_to_gb(used_bytes)
    max_cap = _floor_to_gb(available_for_node)

    if max_cap < min_cap:
        max_cap = min_cap

    return StorageInfo(
        capacity_bytes=settings.capacity_bytes,
        used_bytes=used_bytes,
        disk_free_bytes=disk.free,
        disk_total_bytes=disk.total,
        min_capacity_bytes=min_cap,
        max_capacity_bytes=max_cap,
    )


@router.patch("", response_model=StorageInfo)
async def update_storage_capacity(body: StoragePatch, request: Request) -> StorageInfo:
    """
    Update the node's advertised storage capacity.

    Validates the new value is within [min_capacity_bytes, max_capacity_bytes].
    Persists the new value to the .env file and updates the live Settings object
    so the running process reflects the change immediately.
    Triggers a coordinator heartbeat so the coordinator learns the new capacity.
    Returns the updated StorageInfo.
    """
    store = request.app.state.shard_store
    settings = request.app.state.settings
    coordinator = request.app.state.coordinator
    registration = request.app.state.registration

    used_bytes: int = store.total_used_bytes()
    storage_dir: Path = settings.storage_dir
    storage_dir.mkdir(parents=True, exist_ok=True)
    disk = shutil.disk_usage(str(storage_dir))

    available_for_node = disk.free + used_bytes
    min_cap = _ceil_to_gb(used_bytes)
    max_cap = _floor_to_gb(available_for_node)
    if max_cap < min_cap:
        max_cap = min_cap

    new_capacity = body.capacity_bytes

    if new_capacity < min_cap:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"DSS: capacity cannot be less than current shard usage "
                f"({min_cap // _GB} GB required, {new_capacity // _GB} GB requested)"
            ),
        )
    if new_capacity > max_cap:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"DSS: capacity exceeds available disk space "
                f"(max {max_cap // _GB} GB, {new_capacity // _GB} GB requested)"
            ),
        )

    _update_env_var("DSS_CAPACITY", str(new_capacity))
    
    os.environ["DSS_CAPACITY"] = str(new_capacity)

    object.__setattr__(settings, "capacity_bytes", new_capacity)

    object.__setattr__(registration, "capacity_bytes", new_capacity)

    if coordinator.is_registered:
        try:
            await coordinator.register(registration)
            logger.info("DSS coordinator notified of new capacity: %d bytes", new_capacity)
        except Exception as exc:
            logger.warning("DSS coordinator capacity sync failed (will retry on heartbeat): %s", exc)

    logger.info("DSS storage capacity updated: %d bytes", new_capacity)

    return StorageInfo(
        capacity_bytes=new_capacity,
        used_bytes=used_bytes,
        disk_free_bytes=disk.free,
        disk_total_bytes=disk.total,
        min_capacity_bytes=min_cap,
        max_capacity_bytes=max_cap,
    )
