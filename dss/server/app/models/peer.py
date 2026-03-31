"""
Purpose: In-memory domain model for DSS peer node state managed by the coordinator.
Responsibilities:
    - Define the mutable PeerRecord dataclass used internally by PeerRegistry.
    - Provide conversion helpers to/from the Pydantic PeerInfo schema.
Dependencies: dss.shared.schemas.peer
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from dss.shared.schemas.peer import PeerInfo, PeerStatus


@dataclass
class PeerRecord:
    """Mutable in-memory representation of a registered DSS peer node."""

    node_id: str
    host: str
    port: int
    public_key_pem: str
    capacity_bytes: int
    used_bytes: int = 0
    status: str = PeerStatus.ONLINE
    registered_at: datetime = field(default_factory=datetime.utcnow)
    last_heartbeat: Optional[datetime] = None

    def to_schema(self) -> PeerInfo:
        """Convert this record to a PeerInfo Pydantic schema for API serialization."""
        return PeerInfo(
            node_id=self.node_id,
            host=self.host,
            port=self.port,
            public_key_pem=self.public_key_pem,
            capacity_bytes=self.capacity_bytes,
            used_bytes=self.used_bytes,
            status=self.status,
            registered_at=self.registered_at,
            last_heartbeat=self.last_heartbeat,
        )

    @classmethod
    def from_schema(cls, info: PeerInfo) -> "PeerRecord":
        """Construct a PeerRecord from a PeerInfo Pydantic schema."""
        return cls(
            node_id=info.node_id,
            host=info.host,
            port=info.port,
            public_key_pem=info.public_key_pem,
            capacity_bytes=info.capacity_bytes,
            used_bytes=info.used_bytes,
            status=info.status,
            registered_at=info.registered_at,
            last_heartbeat=info.last_heartbeat,
        )
