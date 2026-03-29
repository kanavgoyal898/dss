"""
Purpose: DSS Coordinator admin API routes — login, health, network policy, shard stats.
Responsibilities:
    - POST /admin/login           — validate admin password, issue JWT for the dashboard.
    - GET  /admin/health          — return system health summary.
    - GET  /admin/network         — return current network mode and allowed IPs.
    - POST /admin/network/mode    — update the network mode.
    - POST /admin/network/allowed-ips — replace the allowed IP allowlist.
    - GET  /admin/shards          — return per-node shard distribution counts.
Dependencies: fastapi, dss.server.app.core.auth, dss.server.app.core.config,
              dss.server.app.core.dependencies, dss.server.app.services.*
"""

import secrets
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, status

from dss.server.app.core.auth import create_admin_token, require_peer_auth
from dss.server.app.core.config import Settings, get_settings
from dss.server.app.core.dependencies import (
    get_health_monitor,
    get_network_policy,
    get_shard_mapper,
)
from dss.server.app.services.health_monitor import HealthMonitor
from dss.server.app.services.network_policy import NetworkPolicy
from dss.server.app.services.shard_mapper import ShardMapper

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/login")
async def admin_login(
    body: dict,
    request: Request,
    settings: Settings = Depends(get_settings),
) -> dict:
    """
    Authenticate the admin dashboard with a password and return a JWT token.

    If DSS_ADMIN_PASSWORD is set, the provided password must match it exactly.
    If DSS_ADMIN_PASSWORD is empty (default for development / Electron use), any
    non-empty password is accepted — the Electron launcher sets a random secret
    so only the person who launched the coordinator can log in.

    Returns {"access_token": "<jwt>", "token_type": "bearer"} on success.
    Raises HTTP 401 on incorrect password.
    """
    password = body.get("password", "")
    if not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password is required.",
        )

    configured = settings.admin_password
    if configured:
        if not secrets.compare_digest(password, configured):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect password.",
            )
    token = create_admin_token(settings)
    return {"access_token": token, "token_type": "bearer"}


@router.get("/health")
async def get_health(
    _: str = Depends(require_peer_auth),
    monitor: HealthMonitor = Depends(get_health_monitor),
) -> dict:
    """Return a DSS system health summary for the Admin Dashboard."""
    return await monitor.get_health_summary()


@router.get("/network")
async def get_network(
    _: str = Depends(require_peer_auth),
    policy: NetworkPolicy = Depends(get_network_policy),
) -> dict:
    """Return the current DSS network mode and allowed IP configuration."""
    return {
        "mode": await policy.get_mode(),
        "allowed_ips": await policy.get_allowed_ips(),
    }


@router.post("/network/mode")
async def set_network_mode(
    body: dict,
    _: str = Depends(require_peer_auth),
    policy: NetworkPolicy = Depends(get_network_policy),
) -> dict:
    """
    Update the DSS network mode.
    Expects JSON body: {"mode": "global" | "lan" | "allowlist"}
    """
    mode = body.get("mode", "")
    try:
        await policy.set_mode(mode)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return {"mode": mode}


@router.post("/network/allowed-ips")
async def set_allowed_ips(
    body: dict,
    _: str = Depends(require_peer_auth),
    policy: NetworkPolicy = Depends(get_network_policy),
) -> dict:
    """
    Replace the DSS allowed IP allowlist.
    Expects JSON body: {"ips": ["192.168.1.0/24", "10.0.0.5"]}
    """
    ips: List[str] = body.get("ips", [])
    await policy.set_allowed_ips(ips)
    return {"allowed_ips": ips}


@router.get("/shards")
async def get_shard_distribution(
    _: str = Depends(require_peer_auth),
    mapper: ShardMapper = Depends(get_shard_mapper),
) -> dict:
    """Return a per-node shard count map for DSS Admin Dashboard visualisation."""
    counts = await mapper.get_node_shard_counts()
    return {"shard_counts": counts}
