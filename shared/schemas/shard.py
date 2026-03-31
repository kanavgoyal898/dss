"""
Purpose: Pydantic schema definitions for DSS shard entities.
Responsibilities: Define ShardInfo, ShardLocation, and ShardVerification shapes
    used by the coordinator metadata store and peer node shard API.
Dependencies: pydantic
"""

from pydantic import BaseModel, Field


class ShardLocation(BaseModel):
    shard_index: int = Field(..., ge=0, description="Zero-based shard index within the Reed-Solomon block")
    node_id: str = Field(..., description="ID of the peer node storing this shard")
    host: str
    port: int


class ShardInfo(BaseModel):
    shard_id: str = Field(..., description="Globally unique shard identifier: <file_id>-<shard_index>")
    file_id: str
    shard_index: int
    total_shards: int = Field(..., description="Total n in (k, n) Reed-Solomon scheme")
    data_shards: int = Field(..., description="Data shards k in (k, n) Reed-Solomon scheme")
    size_bytes: int
    sha256: str = Field(..., description="Hex-encoded SHA-256 digest of the raw shard bytes")
    node_id: str


class ShardVerification(BaseModel):
    shard_id: str
    node_id: str
    sha256_valid: bool
    error: str = ""
