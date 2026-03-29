"""
Purpose: DSS Peer Node upload pipeline — full file upload orchestration.
Responsibilities:
    - Accept raw bytes, run: compress → AES-256-GCM encrypt → Reed-Solomon encode
      → distribute shards concurrently → report completion to coordinator.
    - Generate AES key/nonce per file; wrap key with owner RSA public key.
    - Record exact ciphertext_size before RS padding for correct reconstruction.
    - Invoke an optional progress callback after each shard push.
    - Retry individual shard pushes on transient HTTP failures.
Dependencies: asyncio, zlib, httpx, dss.shared.crypto, dss.shared.encoding,
              dss.client.app.services.coordinator_client, dss.client.app.core.identity
"""

import asyncio
import logging
import zlib
from pathlib import Path
from typing import Callable, List, Optional

import httpx

from dss.client.app.core.identity import NodeIdentity
from dss.client.app.services.coordinator_client import CoordinatorClient
from dss.shared.crypto.aes_utils import (
    aes_encrypt,
    generate_aes_key,
    generate_nonce,
    nonce_to_b64,
    sha256_digest,
)
from dss.shared.crypto.rsa_utils import rsa_encrypt
from dss.shared.encoding.reed_solomon import encode_shards
from dss.shared.schemas.file import FileMetadata, FileUploadComplete, FileUploadInit
from dss.shared.schemas.shard import ShardLocation

logger = logging.getLogger("dss.upload")


class UploadPipeline:
    """Executes the full DSS file upload pipeline."""

    def __init__(
        self,
        coordinator: CoordinatorClient,
        identity: NodeIdentity,
        data_shards: int = 4,
        total_shards: int = 6,
        chunk_size: int = 1024 * 1024,
    ) -> None:
        """Initialise the pipeline with coordinator client and node identity."""
        self._coordinator = coordinator
        self._identity = identity
        self._data_shards = data_shards
        self._total_shards = total_shards
        self._chunk_size = chunk_size

    async def upload(self, file_path: Path, progress_cb: Optional[Callable] = None) -> FileMetadata:
        """
        Execute the upload pipeline for a file at the given path.
        Returns FileMetadata on success; raises RuntimeError on pipeline failure.
        """
        raw_bytes = file_path.read_bytes()
        return await self.upload_bytes(file_path.name, raw_bytes, progress_cb=progress_cb)

    async def upload_bytes(
        self,
        filename: str,
        raw_bytes: bytes,
        progress_cb: Optional[Callable] = None,
    ) -> FileMetadata:
        """
        Execute the upload pipeline for in-memory file bytes.
        progress_cb(pct: int) is called after each shard is delivered (0-100).
        Returns FileMetadata on success; raises RuntimeError on pipeline failure.
        """
        plaintext_sha256 = sha256_digest(raw_bytes)
        logger.info("DSS upload: %s (%d bytes)", filename, len(raw_bytes))

        compressed = zlib.compress(raw_bytes, level=6)
        aes_key = generate_aes_key()
        nonce = generate_nonce()
        ciphertext = aes_encrypt(aes_key, nonce, compressed)
        ciphertext_size = len(ciphertext)
        encrypted_key_b64 = rsa_encrypt(self._identity.public_key, aes_key)
        nonce_b64 = nonce_to_b64(nonce)

        shards = encode_shards(ciphertext, self._data_shards, self._total_shards)

        file_id, shard_locations = await self._coordinator.init_upload(
            FileUploadInit(
                filename=filename,
                size_bytes=len(raw_bytes),
                owner_node_id=self._identity.node_id,
                data_shards=self._data_shards,
                total_shards=self._total_shards,
            )
        )

        await self._distribute_shards(file_id, shards, shard_locations, progress_cb)

        metadata = await self._coordinator.complete_upload(
            FileUploadComplete(
                file_id=file_id,
                shard_locations=shard_locations,
                encrypted_aes_key=encrypted_key_b64,
                aes_nonce=nonce_b64,
                sha256_plaintext=plaintext_sha256,
                ciphertext_size=ciphertext_size,
            )
        )
        logger.info("DSS upload complete: %s", file_id)
        return metadata

    async def _distribute_shards(
        self,
        file_id: str,
        shards: List[bytes],
        locations: List[ShardLocation],
        progress_cb: Optional[Callable],
    ) -> None:
        """
        Push all shards concurrently to their assigned peer nodes.
        Raises RuntimeError if any shard push fails after retries.
        """
        total = len(locations)
        completed = 0
        lock = asyncio.Lock()

        async def push_and_track(loc: ShardLocation) -> None:
            nonlocal completed
            await self._push_shard_with_retry(file_id, shards[loc.shard_index], loc)
            async with lock:
                completed += 1
                if progress_cb:
                    progress_cb(int(completed / total * 100))

        async with httpx.AsyncClient(timeout=httpx.Timeout(connect=10.0, read=120.0, write=120.0, pool=10.0)) as client:
            self._http_client = client
            tasks = [push_and_track(loc) for loc in locations]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        failures = [r for r in results if isinstance(r, Exception)]
        if failures:
            raise RuntimeError(f"DSS: {len(failures)}/{total} shard transfers failed: {failures[0]}")

    async def _push_shard_with_retry(
        self,
        file_id: str,
        shard_data: bytes,
        location: ShardLocation,
        retries: int = 3,
    ) -> None:
        """Push a single shard with up to retries attempts on transient failure."""
        shard_id = f"{file_id}-{location.shard_index}"
        shard_sha = sha256_digest(shard_data)
        url = f"http://{location.host}:{location.port}/api/v1/shards/{shard_id}"
        last_exc = None
        for attempt in range(retries):
            try:
                resp = await self._http_client.put(
                    url,
                    content=shard_data,
                    headers={
                        "X-DSS-SHA256": shard_sha,
                        "X-DSS-File-ID": file_id,
                        "X-DSS-Shard-Index": str(location.shard_index),
                        "Content-Type": "application/octet-stream",
                    },
                )
                resp.raise_for_status()
                return
            except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as exc:
                last_exc = exc
                if attempt < retries - 1:
                    await asyncio.sleep(1.0 * (attempt + 1))
        raise RuntimeError(f"DSS shard {shard_id} failed after {retries} attempts: {last_exc}")
