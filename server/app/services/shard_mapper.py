"""
Purpose: DSS Coordinator shard mapper — selects target peer nodes for shard placement.
Responsibilities:
    - Select n peer nodes for shard distribution, preferring nodes with available capacity.
    - Return ordered ShardLocation assignments for a given file and shard count.
    - Track per-node shard assignments for visualization and health reporting.
    - Re-evaluate placement when peers go offline (lazy recovery support).
Dependencies: asyncio, dss.server.app.services.peer_registry, dss.shared.schemas.shard
"""

import asyncio
from typing import Dict, List, Optional

from dss.server.app.services.peer_registry import PeerRegistry
from dss.shared.schemas.peer import PeerInfo
from dss.shared.schemas.shard import ShardLocation


class ShardMapper:
    """Selects peer nodes for shard placement using a capacity-aware greedy strategy."""

    def __init__(self, peer_registry: PeerRegistry) -> None:
        """Initialise the ShardMapper with a reference to the live PeerRegistry."""
        self._registry = peer_registry
        self._node_shard_counts: Dict[str, int] = {}
        self._lock = asyncio.Lock()

    async def select_nodes_for_shards(
        self, total_shards: int, exclude_nodes: Optional[List[str]] = None
    ) -> List[PeerInfo]:
        """
        Select up to total_shards online peer nodes for shard placement.
        Sorts candidates by (shard_count ASC, free_bytes DESC) to balance load.
        Raises RuntimeError if fewer than total_shards online peers are available.
        """
        exclude = set(exclude_nodes or [])
        online = [p for p in await self._registry.get_online_peers() if p.node_id not in exclude]
        if len(online) < total_shards:
            raise RuntimeError(
                f"DSS: need {total_shards} online peers for shard distribution, "
                f"only {len(online)} available"
            )

        async with self._lock:
            def sort_key(peer: PeerInfo) -> tuple:
                count = self._node_shard_counts.get(peer.node_id, 0)
                free = peer.capacity_bytes - peer.used_bytes
                return (count, -free)

            selected = sorted(online, key=sort_key)[:total_shards]
            for peer in selected:
                self._node_shard_counts[peer.node_id] = (
                    self._node_shard_counts.get(peer.node_id, 0) + 1
                )
        return selected

    async def build_shard_locations(
        self, file_id: str, total_shards: int
    ) -> List[ShardLocation]:
        """
        Return a list of ShardLocation schemas for all shards of a file.
        Delegates node selection to select_nodes_for_shards.
        """
        selected_peers = await self.select_nodes_for_shards(total_shards)
        return [
            ShardLocation(
                shard_index=i,
                node_id=peer.node_id,
                host=peer.host,
                port=peer.port,
            )
            for i, peer in enumerate(selected_peers)
        ]

    async def get_node_shard_counts(self) -> Dict[str, int]:
        """Return a snapshot of per-node assigned shard counts."""
        async with self._lock:
            return dict(self._node_shard_counts)

    async def decrement_node_shard_count(self, node_id: str) -> None:
        """Decrement the shard count for a node (called on lazy recovery eviction)."""
        async with self._lock:
            if node_id in self._node_shard_counts:
                self._node_shard_counts[node_id] = max(
                    0, self._node_shard_counts[node_id] - 1
                )
