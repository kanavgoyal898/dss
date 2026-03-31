"""
Purpose: DSS Peer Node shard storage API routes — receive and serve shard bytes.
Responsibilities:
    - PUT /shards/{shard_id} — accept inbound shard bytes from coordinator-assigned upload.
    - GET /shards/{shard_id} — serve raw shard bytes to downloading peers.
    - GET /shards            — list all locally stored shards with metadata.
    - DELETE /shards/{shard_id} — remove a stored shard (admin/recovery use).
Dependencies: fastapi, dss.client.app.storage.shard_store, dss.shared.crypto.aes_utils
"""

import logging

from fastapi import APIRouter, HTTPException, Request, Response, status

from dss.client.app.storage.shard_store import ShardStore
from dss.shared.crypto.aes_utils import sha256_digest

logger = logging.getLogger("dss.shards_api")

router = APIRouter(prefix="/api/v1/shards", tags=["shards"])


def get_shard_store(request: Request) -> ShardStore:
    """Extract the ShardStore singleton from application state."""
    return request.app.state.shard_store


@router.put("/{shard_id}", status_code=status.HTTP_204_NO_CONTENT)
async def receive_shard(
    shard_id: str,
    request: Request,
) -> None:
    """
    Accept raw shard bytes via HTTP PUT.
    Verifies the SHA-256 header against the received bytes before persisting.
    Returns HTTP 400 if the integrity check fails.
    """
    store = get_shard_store(request)
    expected_sha = request.headers.get("X-DSS-SHA256", "")
    data = await request.body()

    actual_sha = sha256_digest(data)
    if expected_sha and actual_sha != expected_sha:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"DSS: shard {shard_id} integrity check failed",
        )

    store.write_shard(shard_id, data, actual_sha)
    logger.debug("DSS shard received: %s (%d bytes)", shard_id, len(data))


@router.get("/{shard_id}")
async def serve_shard(shard_id: str, request: Request) -> Response:
    """
    Return raw shard bytes for the given shard_id.
    Returns HTTP 404 if the shard is not stored locally.
    Returns HTTP 409 if stored shard fails local integrity verification.
    """
    store = get_shard_store(request)
    if not store.verify_shard(shard_id):
        data = store.read_shard(shard_id)
        if data is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"DSS: shard {shard_id} not found",
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"DSS: shard {shard_id} integrity verification failed",
        )
    data = store.read_shard(shard_id)
    return Response(content=data, media_type="application/octet-stream")


@router.get("")
async def list_shards(request: Request) -> dict:
    """Return a list of all locally stored shard metadata records."""
    store = get_shard_store(request)
    return {"shards": store.list_shards(), "total_used_bytes": store.total_used_bytes()}


@router.delete("/{shard_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_shard(shard_id: str, request: Request) -> None:
    """Delete a stored shard by shard_id. Returns HTTP 404 if not present."""
    store = get_shard_store(request)
    deleted = store.delete_shard(shard_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DSS: shard {shard_id} not found",
        )
