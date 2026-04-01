"""
Purpose: DSS Coordinator file metadata API routes.
Responsibilities:
    - POST /files/init      — open a new upload session, return file_id + shard targets.
    - POST /files/complete  — finalise an upload with shard locations and crypto metadata.
    - GET  /files           — list files owned by the requesting node (admin sees all).
    - GET  /files/{file_id} — retrieve metadata for a specific file (owner or admin only).
    - GET  /files/{file_id}/download — return shard locations and keys for download
                                       (owner or admin only).
    - DELETE /files/{file_id} — delete all peer shards then purge coordinator metadata
                                 (owner or admin only).
Dependencies: fastapi, asyncio, httpx, dss.server.app.core.auth,
              dss.server.app.core.dependencies, dss.server.app.services.metadata_store,
              dss.server.app.services.shard_mapper, dss.shared.schemas.file
"""

import asyncio
import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, status

from dss.server.app.core.auth import ADMIN_SUBJECT, require_peer_auth
from dss.server.app.core.dependencies import get_metadata_store, get_shard_mapper
from dss.server.app.services.metadata_store import MetadataStore
from dss.server.app.services.shard_mapper import ShardMapper
from dss.shared.schemas.file import (
    FileDownloadResponse,
    FileMetadata,
    FileUploadComplete,
    FileUploadInit,
)

logger = logging.getLogger("dss.files_api")

router = APIRouter(prefix="/files", tags=["files"])

_DELETE_TIMEOUT = httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0)


def _is_admin(node_id: str) -> bool:
    """Return True when the caller authenticated as the admin dashboard."""
    return node_id == ADMIN_SUBJECT


@router.post("/init", response_model=dict)
async def init_upload(
    init: FileUploadInit,
    _: str = Depends(require_peer_auth),
    store: MetadataStore = Depends(get_metadata_store),
    mapper: ShardMapper = Depends(get_shard_mapper),
) -> dict:
    """
    Initialise a file upload session.
    Allocates a file_id and selects target peer nodes for each shard.
    Returns file_id and a list of ShardLocation assignments.
    """
    file_id = await store.init_upload(init)
    try:
        shard_locations = await mapper.build_shard_locations(file_id, init.total_shards)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    return {
        "file_id": file_id,
        "shard_locations": [loc.dict() for loc in shard_locations],
    }


@router.post("/complete", response_model=FileMetadata)
async def complete_upload(
    complete: FileUploadComplete,
    node_id: str = Depends(require_peer_auth),
    store: MetadataStore = Depends(get_metadata_store),
) -> FileMetadata:
    """
    Finalise an upload session.
    Stores shard locations, encrypted AES key, nonce, plaintext SHA-256, and ciphertext size.
    Only the node that initiated the upload (matching owner_node_id) may complete it.
    Returns the completed FileMetadata record.
    """
    pending = await store.get_file(complete.file_id)
    if pending is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DSS: upload session {complete.file_id} not found",
        )
    if not _is_admin(node_id) and pending.owner_node_id != node_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="DSS: only the uploading node may complete this upload session",
        )
    result = await store.complete_upload(complete)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DSS: upload session {complete.file_id} not found",
        )
    return result


@router.get("", response_model=list[FileMetadata])
async def list_files(
    node_id: str = Depends(require_peer_auth),
    store: MetadataStore = Depends(get_metadata_store),
) -> list[FileMetadata]:
    """
    Return file metadata records visible to the caller.
    Admin tokens receive the full list; peer node tokens receive only their own files.
    """
    if _is_admin(node_id):
        return await store.list_files()
    return await store.list_files_by_owner(node_id)


@router.get("/{file_id}", response_model=FileMetadata)
async def get_file(
    file_id: str,
    node_id: str = Depends(require_peer_auth),
    store: MetadataStore = Depends(get_metadata_store),
) -> FileMetadata:
    """
    Return metadata for a specific file by its file_id.
    Raises HTTP 403 when a non-admin node requests a file it does not own.
    """
    meta = await store.get_file(file_id)
    if meta is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DSS: file {file_id} not found",
        )
    if not _is_admin(node_id) and meta.owner_node_id != node_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="DSS: access denied — you are not the owner of this file",
        )
    return meta


@router.get("/{file_id}/download", response_model=FileDownloadResponse)
async def get_download_info(
    file_id: str,
    node_id: str = Depends(require_peer_auth),
    store: MetadataStore = Depends(get_metadata_store),
) -> FileDownloadResponse:
    """
    Return all information needed to download a file:
    shard locations, encrypted AES key, nonce, RS parameters, and ciphertext size.
    Raises HTTP 403 when a non-admin node requests a file it does not own.
    """
    meta = await store.get_file(file_id)
    if meta is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DSS: file {file_id} not found",
        )
    if not _is_admin(node_id) and meta.owner_node_id != node_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="DSS: access denied — you are not the owner of this file",
        )
    return FileDownloadResponse(
        file_id=meta.file_id,
        filename=meta.filename,
        shard_locations=meta.shard_locations,
        encrypted_aes_key=meta.encrypted_aes_key,
        aes_nonce=meta.aes_nonce,
        sha256_plaintext=meta.sha256_plaintext,
        data_shards=meta.data_shards,
        total_shards=meta.total_shards,
        ciphertext_size=meta.ciphertext_size,
    )


@router.delete("/{file_id}")
async def delete_file(
    file_id: str,
    node_id: str = Depends(require_peer_auth),
    store: MetadataStore = Depends(get_metadata_store),
) -> dict:
    """
    Permanently delete a file from DSS.

    Fans out DELETE requests to every peer node that holds a shard for this file,
    then removes the file record from the coordinator metadata store.

    Only the owning node or an admin may delete a file.
    Returns a summary of how many shards were deleted and how many failed.
    HTTP 404 if the file does not exist; HTTP 403 if the caller is not the owner.
    """
    meta = await store.get_file(file_id)
    if meta is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DSS: file {file_id} not found",
        )
    if not _is_admin(node_id) and meta.owner_node_id != node_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="DSS: access denied — you are not the owner of this file",
        )

    deleted_shards = 0
    failed_shards = 0

    async with httpx.AsyncClient(timeout=_DELETE_TIMEOUT) as client:

        async def _delete_one_shard(loc) -> bool:
            """Send DELETE to the peer holding this shard; returns True on success."""
            shard_id = f"{file_id}-{loc.shard_index}"
            url = f"https://{loc.host}/api/v1/shards/{shard_id}"
            try:
                resp = await client.delete(url)
                return resp.status_code in (204, 404)
            except Exception as exc:
                logger.warning("DSS: failed to delete shard %s from %s: %s", shard_id, loc.host, exc)
                return False

        results = await asyncio.gather(
            *[_delete_one_shard(loc) for loc in meta.shard_locations]
        )

    deleted_shards = sum(1 for ok in results if ok)
    failed_shards = sum(1 for ok in results if not ok)

    await store.delete_file(file_id)
    logger.info(
        "DSS file deleted: %s (%s) — %d/%d shards removed",
        file_id,
        meta.filename,
        deleted_shards,
        len(meta.shard_locations),
    )

    return {
        "file_id": file_id,
        "filename": meta.filename,
        "deleted_shards": deleted_shards,
        "failed_shards": failed_shards,
        "total_shards": len(meta.shard_locations),
    }
