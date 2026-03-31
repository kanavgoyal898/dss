"""
Purpose: In-memory domain models for DSS file metadata and shard assignment state.
Responsibilities:
    - Define FileRecord dataclass for coordinator-side file tracking.
    - Define ShardAssignment dataclass for per-shard placement records.
    - Provide schema conversion helpers used by MetadataStore and ShardMapper.
Dependencies: dss.shared.schemas.file, dss.shared.schemas.shard
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

from dss.shared.schemas.file import FileMetadata, FileStatus
from dss.shared.schemas.shard import ShardLocation


@dataclass
class ShardAssignment:
    """Tracks which peer node stores a specific shard."""

    shard_id: str
    file_id: str
    shard_index: int
    node_id: str
    host: str
    port: int
    size_bytes: int
    sha256: str

    def to_location(self) -> ShardLocation:
        """Return the ShardLocation schema view of this assignment."""
        return ShardLocation(
            shard_index=self.shard_index,
            node_id=self.node_id,
            host=self.host,
            port=self.port,
        )


@dataclass
class FileRecord:
    """Coordinator-side metadata record for an uploaded DSS file."""

    file_id: str
    filename: str
    size_bytes: int
    ciphertext_size: int
    owner_node_id: str
    data_shards: int
    total_shards: int
    encrypted_aes_key: str
    aes_nonce: str
    sha256_plaintext: str
    status: str = FileStatus.UPLOADING
    shard_assignments: List[ShardAssignment] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None

    def to_schema(self) -> FileMetadata:
        """Convert this record to a FileMetadata Pydantic schema for API serialization."""
        return FileMetadata(
            file_id=self.file_id,
            filename=self.filename,
            size_bytes=self.size_bytes,
            ciphertext_size=self.ciphertext_size,
            owner_node_id=self.owner_node_id,
            data_shards=self.data_shards,
            total_shards=self.total_shards,
            encrypted_aes_key=self.encrypted_aes_key,
            aes_nonce=self.aes_nonce,
            sha256_plaintext=self.sha256_plaintext,
            status=self.status,
            shard_locations=[a.to_location() for a in self.shard_assignments],
            created_at=self.created_at,
            updated_at=self.updated_at,
        )
