"""
Purpose: DSS Coordinator peer management API routes.
Responsibilities:
    - POST /peers/register — accept peer registration, validate network policy, issue JWT.
    - POST /peers/heartbeat — update peer liveness and disk usage.
    - GET  /peers          — list all registered peers (admin use).
    - GET  /peers/{node_id} — retrieve metadata for a specific peer.
Dependencies: fastapi, dss.server.app.core.auth, dss.server.app.core.dependencies,
              dss.server.app.services.peer_registry, dss.server.app.services.network_policy,
              dss.shared.schemas.peer
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status

from dss.server.app.core.auth import require_peer_auth
from dss.server.app.core.dependencies import get_network_policy, get_peer_registry
from dss.server.app.services.network_policy import NetworkPolicy
from dss.server.app.services.peer_registry import PeerRegistry
from dss.shared.schemas.peer import (
    HeartbeatRequest,
    HeartbeatResponse,
    PeerInfo,
    PeerRegistration,
)

router = APIRouter(prefix="/peers", tags=["peers"])


@router.post("/register", response_model=dict)
async def register_peer(
    request: Request,
    registration: PeerRegistration,
    registry: PeerRegistry = Depends(get_peer_registry),
    policy: NetworkPolicy = Depends(get_network_policy),
) -> dict:
    """
    Register a peer node with the DSS coordinator.
    Validates network policy for the originating IP before issuing a JWT token.
    """
    client_ip = request.client.host
    if not await policy.is_allowed(client_ip):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"DSS: IP {client_ip} is not permitted under current network policy",
        )
    token = await registry.register(registration)
    return {"access_token": token, "token_type": "bearer", "node_id": registration.node_id}


@router.post("/heartbeat", response_model=HeartbeatResponse)
async def heartbeat(
    beat: HeartbeatRequest,
    node_id: str = Depends(require_peer_auth),
    registry: PeerRegistry = Depends(get_peer_registry),
) -> HeartbeatResponse:
    """
    Update liveness and disk usage for an authenticated peer node.
    Returns HTTP 404 if the node is not registered.
    """
    ok = await registry.heartbeat(beat)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DSS: peer {beat.node_id} not registered",
        )
    return HeartbeatResponse(acknowledged=True)


@router.get("", response_model=list[PeerInfo])
async def list_peers(
    registry: PeerRegistry = Depends(get_peer_registry),
    _: str = Depends(require_peer_auth),
) -> list[PeerInfo]:
    """Return a list of all registered DSS peer nodes."""
    return await registry.list_peers()


@router.get("/{node_id}", response_model=PeerInfo)
async def get_peer(
    node_id: str,
    registry: PeerRegistry = Depends(get_peer_registry),
    _: str = Depends(require_peer_auth),
) -> PeerInfo:
    """Return metadata for a specific registered peer node."""
    peer = await registry.get_peer(node_id)
    if peer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DSS: peer {node_id} not found",
        )
    return peer
