"""
Purpose: DSS Peer Node status, configuration, and transfer API routes.
Responsibilities:
    - GET    /node/info                — identity, capacity, coordinator connectivity status.
    - GET    /node/files               — files owned by this node (via coordinator).
    - POST   /node/connect             — configure coordinator URL and register.
    - POST   /node/upload-bytes        — multipart drag-and-drop file upload with SSE progress.
    - POST   /node/download            — trigger download pipeline for a file_id.
    - DELETE /node/files/{file_id}     — instruct coordinator to delete file + all shards.
Dependencies: fastapi, python-multipart, dss.client.app.services.*
"""

import asyncio
import json
import logging
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Request, UploadFile, status
from fastapi.responses import StreamingResponse

from dss.client.app.services.download_pipeline import DownloadPipeline
from dss.client.app.services.upload_pipeline import UploadPipeline

logger = logging.getLogger("dss.node_api")

router = APIRouter(prefix="/api/v1/node", tags=["node"])


@router.get("/info")
async def node_info(request: Request) -> dict:
    """Return node identity, storage stats, and coordinator connectivity status."""
    identity = request.app.state.identity
    store = request.app.state.shard_store
    settings = request.app.state.settings
    coordinator = request.app.state.coordinator
    return {
        "node_id": identity.node_id,
        "public_key_pem": identity.public_key_pem,
        "coordinator_url": coordinator.base_url,
        "coordinator_connected": coordinator.is_registered,
        "advertised_host": settings.advertised_host,
        "port": settings.port,
        "capacity_bytes": settings.capacity_bytes,
        "used_bytes": store.total_used_bytes(),
        "shard_count": len(store.list_shards()),
    }


@router.post("/connect")
async def connect_to_coordinator(body: dict, request: Request) -> dict:
    """
    Configure the coordinator URL and register this node.
    Expects JSON: {"coordinator_url": "http://host:port"}
    Returns connection status and node identity on success.
    Raises HTTP 502 if the coordinator cannot be reached.
    """
    coordinator_url = body.get("coordinator_url", "").strip()
    if not coordinator_url:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="coordinator_url is required")

    coordinator = request.app.state.coordinator
    registration = request.app.state.registration

    await coordinator.update_base_url(coordinator_url)
    try:
        await coordinator.register(registration)
        logger.info("DSS node connected to coordinator: %s", coordinator_url)
        return {
            "connected": True,
            "coordinator_url": coordinator_url,
            "node_id": registration.node_id,
        }
    except Exception as exc:
        logger.warning("DSS coordinator connection failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Cannot reach coordinator at {coordinator_url}. Make sure the Coordinator is running and the address is correct.",
        )


@router.get("/files")
async def list_my_files(request: Request) -> dict:
    """Return all files tracked by the coordinator. Requires an active connection."""
    coordinator = request.app.state.coordinator
    if not coordinator.is_registered:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Not connected to a coordinator. Use the Connect button first.",
        )
    try:
        files = await coordinator.list_my_files()
        return {"files": [f.dict() for f in files]}
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Lost connection to coordinator: {exc}",
        )


@router.delete("/files/{file_id}")
async def delete_file(file_id: str, request: Request) -> dict:
    """
    Delete a file and all its shards across every peer node.

    Proxies the delete request to the coordinator, which fans out shard deletion
    to each peer and then removes the file record from its metadata store.

    Returns a deletion summary with counts of deleted and failed shards.
    Raises HTTP 503 if not connected; HTTP 404/403 are forwarded from the coordinator.
    """
    coordinator = request.app.state.coordinator
    if not coordinator.is_registered:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Not connected to a coordinator. Connect first via the dashboard.",
        )
    if not file_id.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="file_id is required")
    try:
        result = await coordinator.delete_file(file_id)
        logger.info("DSS file deletion complete: %s", file_id)
        return result
    except Exception as exc:
        logger.error("DSS file deletion failed: %s — %s", file_id, exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"File deletion failed: {exc}",
        )


@router.post("/upload-bytes")
async def upload_file_bytes(request: Request, file: UploadFile = File(...)) -> StreamingResponse:
    """
    Accept a multipart file upload and run the DSS upload pipeline.
    Streams Server-Sent Events with progress updates (pct field) and a final result or error.
    """
    coordinator = request.app.state.coordinator
    if not coordinator.is_registered:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Not connected to a coordinator. Connect first via the dashboard.",
        )

    raw_bytes = await file.read()
    filename = file.filename or "upload"
    pipeline: UploadPipeline = request.app.state.upload_pipeline

    queue: asyncio.Queue = asyncio.Queue()

    def progress_cb(pct: int) -> None:
        queue.put_nowait({"type": "progress", "pct": pct})

    async def run_upload() -> None:
        try:
            metadata = await pipeline.upload_bytes(filename, raw_bytes, progress_cb=progress_cb)
            queue.put_nowait({
                "type": "done",
                "file_id": metadata.file_id,
                "filename": metadata.filename,
                "status": metadata.status,
            })
        except Exception as exc:
            logger.error("DSS upload failed: %s", exc)
            queue.put_nowait({"type": "error", "detail": str(exc)})

    async def event_stream():
        task = asyncio.create_task(run_upload())
        while True:
            try:
                msg = await asyncio.wait_for(queue.get(), timeout=120.0)
                yield f"data: {json.dumps(msg)}\n\n"
                if msg["type"] in ("done", "error"):
                    break
            except asyncio.TimeoutError:
                yield f"data: {json.dumps({'type': 'error', 'detail': 'Upload timed out'})}\n\n"
                break
        task.cancel()

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/download")
async def trigger_download(body: dict, request: Request) -> StreamingResponse:
    """
    Trigger the download pipeline for a file_id and stream progress events.
    Expects JSON: {"file_id": "...", "output_path": "..."} (output_path optional).
    """
    coordinator = request.app.state.coordinator
    if not coordinator.is_registered:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Not connected to a coordinator. Connect first via the dashboard.",
        )
    file_id = body.get("file_id", "").strip()
    if not file_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="file_id is required")

    output_path_str = body.get("output_path", "")
    output_path = Path(output_path_str) if output_path_str else Path.home() / "Downloads" / file_id

    pipeline: DownloadPipeline = request.app.state.download_pipeline
    queue: asyncio.Queue = asyncio.Queue()

    def progress_cb(pct: int) -> None:
        queue.put_nowait({"type": "progress", "pct": pct})

    async def run_download() -> None:
        try:
            saved = await pipeline.download(file_id, output_path, progress_cb=progress_cb)
            queue.put_nowait({"type": "done", "file_id": file_id, "saved_to": str(saved)})
        except Exception as exc:
            logger.error("DSS download failed: %s", exc)
            queue.put_nowait({"type": "error", "detail": str(exc)})

    async def event_stream():
        task = asyncio.create_task(run_download())
        while True:
            try:
                msg = await asyncio.wait_for(queue.get(), timeout=300.0)
                yield f"data: {json.dumps(msg)}\n\n"
                if msg["type"] in ("done", "error"):
                    break
            except asyncio.TimeoutError:
                yield f"data: {json.dumps({'type': 'error', 'detail': 'Download timed out'})}\n\n"
                break
        task.cancel()

    return StreamingResponse(event_stream(), media_type="text/event-stream")
