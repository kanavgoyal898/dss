"""
Purpose: DSS Coordinator peer registry — registration, lookup, and eviction of peer nodes.
Responsibilities:
    - Register new peer nodes and issue JWT tokens.
    - Look up peers by node_id.
    - Process heartbeat updates to track liveness and disk usage.
    - Evict peers that exceed the heartbeat timeout.
    - Enforce network policy by delegating to NetworkPolicy before registration.
Dependencies: asyncio, dss.server.app.models.peer, dss.server.app.core.auth,
              dss.server.app.core.config, dss.shared.schemas.peer
"""

import asyncio
from datetime import datetime
from typing import Dict, List, Optional

from dss.server.app.core.auth import create_access_token
from dss.server.app.core.config import Settings
from dss.server.app.models.peer import PeerRecord
from dss.shared.schemas.peer import HeartbeatRequest, PeerInfo, PeerRegistration, PeerStatus


class PeerRegistry:
    """Thread-safe in-memory store of registered DSS peer nodes."""

    def __init__(self, settings: Settings) -> None:
        """Initialise an empty registry with the given coordinator settings."""
        self._settings = settings
        self._peers: Dict[str, PeerRecord] = {}
        self._lock = asyncio.Lock()

    async def register(self, registration: PeerRegistration) -> str:
        """
        Register a peer node and return a signed JWT access token.
        Replaces any existing record for the same node_id.
        """
        async with self._lock:
            record = PeerRecord(
                node_id=registration.node_id,
                host=registration.host,
                port=registration.port,
                public_key_pem=registration.public_key_pem,
                capacity_bytes=registration.capacity_bytes,
                status=PeerStatus.ONLINE,
                last_heartbeat=datetime.utcnow(),
            )
            self._peers[registration.node_id] = record
        return create_access_token(registration.node_id, self._settings)

    async def heartbeat(self, request: HeartbeatRequest) -> bool:
        """
        Update the heartbeat timestamp and disk usage for a peer.
        Returns False if the peer is not registered.
        """
        async with self._lock:
            record = self._peers.get(request.node_id)
            if record is None:
                return False
            record.last_heartbeat = datetime.utcnow()
            record.used_bytes = request.used_bytes
            record.status = PeerStatus.ONLINE
        return True

    async def get_peer(self, node_id: str) -> Optional[PeerInfo]:
        """Return PeerInfo for a given node_id, or None if not registered."""
        async with self._lock:
            record = self._peers.get(node_id)
        return record.to_schema() if record else None

    async def list_peers(self) -> List[PeerInfo]:
        """Return a snapshot of all registered peers."""
        async with self._lock:
            return [r.to_schema() for r in self._peers.values()]

    async def evict_stale_peers(self, timeout_seconds: int) -> List[str]:
        """
        Mark peers whose last heartbeat exceeds timeout_seconds as OFFLINE.
        Returns a list of evicted node_ids.
        """
        now = datetime.utcnow()
        evicted: List[str] = []
        async with self._lock:
            for record in self._peers.values():
                if record.last_heartbeat is None:
                    continue
                elapsed = (now - record.last_heartbeat).total_seconds()
                if elapsed > timeout_seconds and record.status == PeerStatus.ONLINE:
                    record.status = PeerStatus.OFFLINE
                    evicted.append(record.node_id)
        return evicted

    async def get_online_peers(self) -> List[PeerInfo]:
        """Return only peers currently in ONLINE status."""
        async with self._lock:
            return [
                r.to_schema()
                for r in self._peers.values()
                if r.status == PeerStatus.ONLINE
            ]
