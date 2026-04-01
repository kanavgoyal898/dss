"""
Purpose: DSS Coordinator metadata store — file record lifecycle management.
Responsibilities:
    - Create, update, and retrieve FileRecord instances for uploaded files.
    - Persist shard assignment data returned by completing upload sessions.
    - List all files or files owned by a specific peer node.
    - Mark file status transitions (UPLOADING → AVAILABLE → DEGRADED).
    - Permanently delete file records from the store.
Dependencies: asyncio, uuid, dss.server.app.models.file, dss.shared.schemas.file
"""

import asyncio
import uuid
from datetime import datetime
from typing import Dict, List, Optional

from dss.server.app.models.file import FileRecord, ShardAssignment
from dss.shared.schemas.file import (
    FileMetadata,
    FileStatus,
    FileUploadComplete,
    FileUploadInit,
)
from dss.shared.schemas.shard import ShardLocation


class MetadataStore:
    """Thread-safe in-memory metadata store for DSS file records."""

    def __init__(self) -> None:
        """Initialise an empty metadata store."""
        self._files: Dict[str, FileRecord] = {}
        self._lock = asyncio.Lock()

    async def init_upload(self, init: FileUploadInit) -> str:
        """
        Create a pending FileRecord for a new upload session.
        Returns the generated file_id.
        """
        file_id = uuid.uuid4().hex
        record = FileRecord(
            file_id=file_id,
            filename=init.filename,
            size_bytes=init.size_bytes,
            ciphertext_size=0,
            owner_node_id=init.owner_node_id,
            data_shards=init.data_shards,
            total_shards=init.total_shards,
            encrypted_aes_key="",
            aes_nonce="",
            sha256_plaintext="",
            status=FileStatus.UPLOADING,
        )
        async with self._lock:
            self._files[file_id] = record
        return file_id

    async def complete_upload(self, complete: FileUploadComplete) -> Optional[FileMetadata]:
        """
        Finalise an upload by storing shard locations and crypto material.
        Returns the updated FileMetadata schema, or None if file_id is unknown.
        """
        async with self._lock:
            record = self._files.get(complete.file_id)
            if record is None:
                return None
            record.encrypted_aes_key = complete.encrypted_aes_key
            record.aes_nonce = complete.aes_nonce
            record.sha256_plaintext = complete.sha256_plaintext
            record.ciphertext_size = complete.ciphertext_size
            record.status = FileStatus.AVAILABLE
            record.updated_at = datetime.utcnow()
            record.shard_assignments = [
                self._location_to_assignment(complete.file_id, loc, record)
                for loc in complete.shard_locations
            ]
            return record.to_schema()

    async def get_file(self, file_id: str) -> Optional[FileMetadata]:
        """Return FileMetadata for a given file_id, or None if not found."""
        async with self._lock:
            record = self._files.get(file_id)
        return record.to_schema() if record else None

    async def list_files(self) -> List[FileMetadata]:
        """Return a snapshot of all file metadata records."""
        async with self._lock:
            return [r.to_schema() for r in self._files.values()]

    async def list_files_by_owner(self, owner_node_id: str) -> List[FileMetadata]:
        """Return metadata for all files owned by a specific peer node."""
        async with self._lock:
            return [
                r.to_schema()
                for r in self._files.values()
                if r.owner_node_id == owner_node_id
            ]

    async def delete_file(self, file_id: str) -> Optional[FileMetadata]:
        """
        Permanently remove a file record from the metadata store.
        Returns the deleted FileMetadata schema, or None if the file_id was not found.
        """
        async with self._lock:
            record = self._files.pop(file_id, None)
        return record.to_schema() if record else None

    async def mark_degraded(self, file_id: str) -> None:
        """Transition a file's status to DEGRADED when shards are unavailable."""
        async with self._lock:
            record = self._files.get(file_id)
            if record:
                record.status = FileStatus.DEGRADED
                record.updated_at = datetime.utcnow()

    async def mark_recovering(self, file_id: str) -> None:
        """Transition a file's status to RECOVERING during lazy re-encoding."""
        async with self._lock:
            record = self._files.get(file_id)
            if record:
                record.status = FileStatus.RECOVERING
                record.updated_at = datetime.utcnow()

    async def files_with_shards_on_node(self, node_id: str) -> List[FileMetadata]:
        """Return all files that have at least one shard assigned to node_id."""
        async with self._lock:
            result = []
            for record in self._files.values():
                if any(a.node_id == node_id for a in record.shard_assignments):
                    result.append(record.to_schema())
            return result

    def _location_to_assignment(
        self,
        file_id: str,
        loc: ShardLocation,
        record: FileRecord,
    ) -> ShardAssignment:
        """Convert a ShardLocation schema into an internal ShardAssignment model."""
        return ShardAssignment(
            shard_id=f"{file_id}-{loc.shard_index}",
            file_id=file_id,
            shard_index=loc.shard_index,
            node_id=loc.node_id,
            host=loc.host,
            port=loc.port,
            size_bytes=0,
            sha256="",
        )
