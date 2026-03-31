"""
Purpose: DSS Peer Node local shard storage — write, read, verify, and list shards on disk.
Responsibilities:
    - Persist raw shard bytes to a structured directory layout under storage_dir.
    - Read shard bytes back by shard_id.
    - Verify stored shard integrity using SHA-256.
    - Enumerate stored shards with their metadata for dashboard reporting.
    - Compute total bytes used across all stored shards.
Dependencies: pathlib, hashlib, json, dss.shared.crypto.aes_utils
"""

import hashlib
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger("dss.storage")

_META_SUFFIX = ".meta.json"
_DATA_SUFFIX = ".shard"


class ShardStore:
    """Manages on-disk storage of DSS erasure-coded shards."""

    def __init__(self, storage_dir: Path) -> None:
        """Initialise the store; creates the storage directory if absent."""
        self._base = storage_dir
        self._base.mkdir(parents=True, exist_ok=True)

    def write_shard(self, shard_id: str, data: bytes, sha256: str) -> None:
        """
        Persist a shard's raw bytes and a JSON metadata sidecar to disk.
        Raises IOError if the write fails.
        """
        shard_path = self._shard_path(shard_id)
        meta_path = self._meta_path(shard_id)
        shard_path.write_bytes(data)
        meta_path.write_text(
            json.dumps({"shard_id": shard_id, "sha256": sha256, "size_bytes": len(data)})
        )
        logger.debug("DSS shard written: %s (%d bytes)", shard_id, len(data))

    def read_shard(self, shard_id: str) -> Optional[bytes]:
        """
        Read and return raw shard bytes from disk.
        Returns None if the shard is not found.
        """
        path = self._shard_path(shard_id)
        if not path.exists():
            logger.warning("DSS shard not found: %s", shard_id)
            return None
        return path.read_bytes()

    def verify_shard(self, shard_id: str) -> bool:
        """
        Verify stored shard integrity by comparing its SHA-256 against stored metadata.
        Returns False if the shard or metadata is missing, or if the digest mismatches.
        """
        data = self.read_shard(shard_id)
        if data is None:
            return False
        meta_path = self._meta_path(shard_id)
        if not meta_path.exists():
            return False
        meta = json.loads(meta_path.read_text())
        actual = hashlib.sha256(data).hexdigest()
        return actual == meta.get("sha256")

    def delete_shard(self, shard_id: str) -> bool:
        """Delete a shard and its metadata from disk. Returns True if deleted."""
        shard_path = self._shard_path(shard_id)
        meta_path = self._meta_path(shard_id)
        deleted = False
        if shard_path.exists():
            shard_path.unlink()
            deleted = True
        if meta_path.exists():
            meta_path.unlink()
        return deleted

    def list_shards(self) -> List[Dict]:
        """
        Return a list of dicts describing all stored shards.
        Each dict includes shard_id, sha256, and size_bytes.
        """
        result = []
        for meta_file in self._base.glob(f"*{_META_SUFFIX}"):
            try:
                result.append(json.loads(meta_file.read_text()))
            except Exception as exc:
                logger.error("DSS failed to read shard metadata %s: %s", meta_file, exc)
        return result

    def total_used_bytes(self) -> int:
        """Return the sum of sizes of all stored shard files in bytes."""
        return sum(p.stat().st_size for p in self._base.glob(f"*{_DATA_SUFFIX}"))

    def _shard_path(self, shard_id: str) -> Path:
        """Return the filesystem path for a shard data file."""
        return self._base / f"{shard_id}{_DATA_SUFFIX}"

    def _meta_path(self, shard_id: str) -> Path:
        """Return the filesystem path for a shard metadata sidecar."""
        return self._base / f"{shard_id}{_META_SUFFIX}"
