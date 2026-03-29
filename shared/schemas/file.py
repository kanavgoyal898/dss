"""
Purpose: Pydantic schema definitions for DSS file metadata entities.
Responsibilities: Define FileMetadata, FileUploadInit, FileUploadComplete, and
    FileDownloadResponse shapes exchanged between coordinator and peer nodes.
Dependencies: pydantic, shared.schemas.shard
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field

from dss.shared.schemas.shard import ShardLocation


class FileStatus(str, Enum):
    UPLOADING = "uploading"
    AVAILABLE = "available"
    DEGRADED = "degraded"
    RECOVERING = "recovering"


class FileUploadInit(BaseModel):
    filename: str
    size_bytes: int = Field(..., ge=1)
    owner_node_id: str
    data_shards: int = Field(default=4, ge=2)
    total_shards: int = Field(default=6, ge=3)


class FileMetadata(BaseModel):
    file_id: str
    filename: str
    size_bytes: int
    ciphertext_size: int = Field(default=0, description="Exact byte length of the AES-GCM ciphertext before Reed-Solomon padding")
    owner_node_id: str
    data_shards: int
    total_shards: int
    encrypted_aes_key: str = Field(..., description="Base64 AES-256 key encrypted with owner RSA public key")
    aes_nonce: str = Field(..., description="Base64 AES-GCM nonce for this file")
    sha256_plaintext: str = Field(..., description="SHA-256 of original plaintext for final integrity check")
    status: FileStatus = FileStatus.UPLOADING
    shard_locations: List[ShardLocation] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None

    class Config:
        use_enum_values = True


class FileUploadComplete(BaseModel):
    file_id: str
    shard_locations: List[ShardLocation]
    encrypted_aes_key: str
    aes_nonce: str
    sha256_plaintext: str
    ciphertext_size: int = Field(..., description="Exact byte length of AES-GCM ciphertext before RS padding")


class FileDownloadResponse(BaseModel):
    file_id: str
    filename: str
    shard_locations: List[ShardLocation]
    encrypted_aes_key: str
    aes_nonce: str
    sha256_plaintext: str
    data_shards: int
    total_shards: int
    ciphertext_size: int
