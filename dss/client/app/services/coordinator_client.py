"""
Purpose: DSS Peer Node HTTP client for communicating with the DSS Coordinator API.
Responsibilities:
    - Register the node and obtain a JWT access token with automatic retry.
    - Send periodic heartbeat updates; mark disconnected on repeated failures.
    - Initialise upload sessions and complete them with shard location reports.
    - Retrieve file download information for a given file_id.
    - List all files tracked by the coordinator.
    - Delete a file and all its shards via the coordinator.
    - Support runtime coordinator URL updates for in-app configuration.
Dependencies: httpx, asyncio, dss.shared.schemas.*
"""

import asyncio
import logging
from typing import List, Optional

import httpx

from dss.shared.schemas.file import FileDownloadResponse, FileMetadata, FileUploadComplete, FileUploadInit
from dss.shared.schemas.peer import HeartbeatRequest, PeerRegistration
from dss.shared.schemas.shard import ShardLocation

logger = logging.getLogger("dss.coordinator_client")

_TIMEOUT = httpx.Timeout(connect=10.0, read=60.0, write=60.0, pool=10.0)
_MAX_RETRIES = 3
_RETRY_DELAY = 1.0


async def _with_retry(coro_factory, retries=_MAX_RETRIES):
    """
    Execute an async operation with exponential back-off retry on transient errors.
    Raises the last exception if all retries are exhausted.
    """
    last_exc = None
    for attempt in range(retries):
        try:
            return await coro_factory()
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            last_exc = exc
            if attempt < retries - 1:
                await asyncio.sleep(_RETRY_DELAY * (attempt + 1))
    raise last_exc


class CoordinatorClient:
    """Async HTTP client for DSS Coordinator API interactions."""

    def __init__(self, base_url: str) -> None:
        """Initialise the client with the coordinator base URL."""
        self._base = base_url.rstrip("/")
        self._token: Optional[str] = None
        self._client = httpx.AsyncClient(timeout=_TIMEOUT)
        self._registered = False

    @property
    def base_url(self) -> str:
        """Return the current coordinator base URL."""
        return self._base

    @property
    def is_registered(self) -> bool:
        """Return True if the node has successfully registered with the coordinator."""
        return self._registered

    @property
    def _headers(self) -> dict:
        """Return authorization headers when a token is available."""
        if self._token:
            return {"Authorization": f"Bearer {self._token}"}
        return {}

    async def update_base_url(self, new_url: str) -> None:
        """
        Update the coordinator base URL and reset authentication state.
        Must be followed by a register() call to re-authenticate.
        """
        self._base = new_url.rstrip("/")
        self._token = None
        self._registered = False

    async def register(self, registration: PeerRegistration) -> str:
        """
        Register with the coordinator and cache the returned JWT token.
        Retries up to _MAX_RETRIES times on transient network errors.
        Raises httpx.HTTPStatusError on HTTP-level failure.
        """
        async def _do():
            resp = await self._client.post(
                f"{self._base}/api/v1/peers/register",
                json=registration.dict(),
                timeout=15.0,
            )
            resp.raise_for_status()
            return resp.json()

        data = await _with_retry(_do)
        self._token = data["access_token"]
        self._registered = True
        logger.info("DSS node registered: %s → %s", data["node_id"], self._base)
        return self._token

    async def heartbeat(self, beat: HeartbeatRequest) -> bool:
        """Send a heartbeat to the coordinator. Returns True on success, False on any error."""
        try:
            resp = await self._client.post(
                f"{self._base}/api/v1/peers/heartbeat",
                json=beat.dict(),
                headers=self._headers,
                timeout=10.0,
            )
            resp.raise_for_status()
            self._registered = True
            return True
        except Exception as exc:
            logger.warning("DSS heartbeat failed: %s", exc)
            self._registered = False
            return False

    async def init_upload(self, init: FileUploadInit) -> tuple[str, List[ShardLocation]]:
        """
        Open an upload session with the coordinator.
        Returns (file_id, list[ShardLocation]) on success.
        """
        resp = await self._client.post(
            f"{self._base}/api/v1/files/init",
            json=init.dict(),
            headers=self._headers,
        )
        resp.raise_for_status()
        data = resp.json()
        locations = [ShardLocation(**loc) for loc in data["shard_locations"]]
        return data["file_id"], locations

    async def complete_upload(self, complete: FileUploadComplete) -> FileMetadata:
        """Finalise an upload session and return the completed FileMetadata."""
        resp = await self._client.post(
            f"{self._base}/api/v1/files/complete",
            json=complete.dict(),
            headers=self._headers,
        )
        resp.raise_for_status()
        return FileMetadata(**resp.json())

    async def get_download_info(self, file_id: str) -> FileDownloadResponse:
        """Retrieve shard locations and crypto metadata needed to reconstruct a file."""
        resp = await self._client.get(
            f"{self._base}/api/v1/files/{file_id}/download",
            headers=self._headers,
        )
        resp.raise_for_status()
        return FileDownloadResponse(**resp.json())

    async def list_my_files(self) -> List[FileMetadata]:
        """Return all files currently tracked by the coordinator."""
        resp = await self._client.get(
            f"{self._base}/api/v1/files",
            headers=self._headers,
        )
        resp.raise_for_status()
        return [FileMetadata(**f) for f in resp.json()]

    async def delete_file(self, file_id: str) -> dict:
        """
        Request the coordinator to delete a file and all its peer shards.
        Returns a summary dict with deleted_shards and failed_shards counts.
        Raises httpx.HTTPStatusError on coordinator-level failure.
        """
        resp = await self._client.delete(
            f"{self._base}/api/v1/files/{file_id}",
            headers=self._headers,
            timeout=30.0,
        )
        resp.raise_for_status()
        return resp.json()

    async def close(self) -> None:
        """Close the underlying HTTP connection pool gracefully."""
        await self._client.aclose()
