"""
Purpose: DSS Peer Node download pipeline — full file retrieval and reconstruction.
Responsibilities:
    - Fetch coordinator metadata to discover shard locations for a file_id.
    - Retrieve available shards concurrently with per-shard retry on failure.
    - Apply Reed-Solomon reconstruction from any data_shards of total available.
    - Decrypt AES-256-GCM ciphertext after unwrapping the key with owner RSA private key.
    - Decompress zlib payload and verify SHA-256 against coordinator metadata.
    - Write reconstructed file to output_path; return path on success.
Dependencies: asyncio, zlib, httpx, dss.shared.crypto, dss.shared.encoding,
              dss.client.app.services.coordinator_client, dss.client.app.core.identity
"""

import asyncio
import logging
import zlib
from pathlib import Path
from typing import Callable, Dict, Optional

import httpx

from dss.client.app.core.identity import NodeIdentity
from dss.client.app.services.coordinator_client import CoordinatorClient
from dss.shared.crypto.aes_utils import aes_decrypt, b64_to_nonce, sha256_digest
from dss.shared.crypto.rsa_utils import rsa_decrypt
from dss.shared.encoding.reed_solomon import decode_shards
from dss.shared.schemas.shard import ShardLocation

logger = logging.getLogger("dss.download")

_FETCH_TIMEOUT = httpx.Timeout(connect=10.0, read=120.0, write=10.0, pool=10.0)


class DownloadPipeline:
    """Executes the full DSS file download and reconstruction pipeline."""

    def __init__(self, coordinator: CoordinatorClient, identity: NodeIdentity) -> None:
        """Initialise the pipeline with coordinator client and node identity."""
        self._coordinator = coordinator
        self._identity = identity

    async def download(
        self,
        file_id: str,
        output_path: Path,
        progress_cb: Optional[Callable] = None,
    ) -> Path:
        """
        Download and reconstruct a file by file_id.
        progress_cb(pct: int) is called as shards are fetched (0-100).
        Writes output to output_path; returns output_path on success.
        Raises RuntimeError on unrecoverable failure or integrity mismatch.
        """
        info = await self._coordinator.get_download_info(file_id)
        logger.info("DSS download: %s (%s)", file_id, info.filename)

        output_path = output_path.parent / info.filename

        total_locs = len(info.shard_locations)
        fetched = 0
        shard_bytes_map: Dict[int, bytes] = {}
        lock = asyncio.Lock()

        async def fetch_one(loc: ShardLocation) -> None:
            nonlocal fetched
            data = await self._fetch_shard_with_retry(file_id, loc)
            async with lock:
                if data is not None:
                    shard_bytes_map[loc.shard_index] = data
                fetched += 1
                if progress_cb:
                    progress_cb(int(fetched / total_locs * 60))

        async with httpx.AsyncClient(timeout=_FETCH_TIMEOUT) as client:
            self._http_client = client
            await asyncio.gather(*[fetch_one(loc) for loc in info.shard_locations])

        if len(shard_bytes_map) < info.data_shards:
            raise RuntimeError(
                f"DSS: only {len(shard_bytes_map)}/{info.data_shards} required shards "
                f"are reachable — file cannot be recovered at this time."
            )

        if progress_cb:
            progress_cb(65)

        ciphertext = decode_shards(
            shard_bytes_map,
            info.data_shards,
            info.total_shards,
            original_size=info.ciphertext_size,
        )

        if progress_cb:
            progress_cb(75)

        aes_key = rsa_decrypt(self._identity.private_key, info.encrypted_aes_key)
        nonce = b64_to_nonce(info.aes_nonce)
        compressed = aes_decrypt(aes_key, nonce, ciphertext)
        raw_bytes = zlib.decompress(compressed)

        actual = sha256_digest(raw_bytes)
        if actual != info.sha256_plaintext:
            raise RuntimeError(
                f"DSS: file integrity check failed — the downloaded data may be corrupted."
            )

        if progress_cb:
            progress_cb(90)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(raw_bytes)
        logger.info("DSS download complete: %s → %s", file_id, output_path)

        if progress_cb:
            progress_cb(100)

        return output_path

    async def _fetch_shard_with_retry(
        self,
        file_id: str,
        location: ShardLocation,
        retries: int = 3,
    ) -> Optional[bytes]:
        """
        Fetch a shard from its assigned peer node with retry on transient errors.
        Returns raw bytes on success, or None if the shard is permanently unavailable.
        """
        shard_id = f"{file_id}-{location.shard_index}"
        url = f"https://{location.host}/api/v1/shards/{shard_id}"
        for attempt in range(retries):
            try:
                resp = await self._http_client.get(url)
                resp.raise_for_status()
                return resp.content
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code in (404, 409):
                    logger.warning("DSS shard %s not available: HTTP %s", shard_id, exc.response.status_code)
                    return None
                if attempt < retries - 1:
                    await asyncio.sleep(1.0 * (attempt + 1))
            except (httpx.ConnectError, httpx.TimeoutException) as exc:
                logger.warning("DSS shard %s fetch error (attempt %d): %s", shard_id, attempt + 1, exc)
                if attempt < retries - 1:
                    await asyncio.sleep(1.0 * (attempt + 1))
        logger.error("DSS shard %s permanently unavailable after %d attempts", shard_id, retries)
        return None
