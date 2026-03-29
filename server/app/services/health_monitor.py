"""
Purpose: DSS Coordinator background health monitor — periodic peer liveness checks.
Responsibilities:
    - Run an asyncio background task that periodically evicts stale peers.
    - Log peer evictions and trigger lazy recovery evaluation via MetadataStore.
    - Expose system health summary for the DSS Admin Dashboard.
Dependencies: asyncio, logging, dss.server.app.services.peer_registry,
              dss.server.app.services.metadata_store, dss.server.app.core.config
"""

import asyncio
import logging
from typing import Any, Dict

from dss.server.app.core.config import Settings
from dss.server.app.services.metadata_store import MetadataStore
from dss.server.app.services.peer_registry import PeerRegistry

logger = logging.getLogger("dss.health")


class HealthMonitor:
    """Runs a periodic background coroutine to check peer liveness and file health."""

    def __init__(
        self,
        peer_registry: PeerRegistry,
        metadata_store: MetadataStore,
        settings: Settings,
    ) -> None:
        """Initialise the monitor with service dependencies and settings."""
        self._registry = peer_registry
        self._store = metadata_store
        self._settings = settings
        self._task: asyncio.Task = None
        self._running = False

    async def start(self) -> None:
        """Start the background health check loop."""
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("DSS health monitor started")

    async def stop(self) -> None:
        """Cancel and await the background task."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("DSS health monitor stopped")

    async def get_health_summary(self) -> Dict[str, Any]:
        """
        Return a dictionary summarising system health for the DSS Admin Dashboard.
        Includes total peer count, online count, and total file count.
        """
        all_peers = await self._registry.list_peers()
        online_peers = await self._registry.get_online_peers()
        all_files = await self._store.list_files()
        return {
            "total_peers": len(all_peers),
            "online_peers": len(online_peers),
            "total_files": len(all_files),
            "available_files": sum(1 for f in all_files if f.status == "available"),
            "degraded_files": sum(1 for f in all_files if f.status == "degraded"),
        }

    async def _loop(self) -> None:
        """Periodic coroutine: evict stale peers and flag degraded files."""
        while self._running:
            await asyncio.sleep(self._settings.health_check_interval_seconds)
            try:
                await self._check_peers()
            except Exception as exc:
                logger.error("DSS health check error: %s", exc)

    async def _check_peers(self) -> None:
        """Evict stale peers and mark files degraded if shards are now unavailable."""
        evicted = await self._registry.evict_stale_peers(
            self._settings.peer_heartbeat_timeout_seconds
        )
        for node_id in evicted:
            logger.warning("DSS peer evicted (heartbeat timeout): %s", node_id)
            affected = await self._store.files_with_shards_on_node(node_id)
            for file_meta in affected:
                online_peers = await self._registry.get_online_peers()
                online_ids = {p.node_id for p in online_peers}
                available_shards = sum(
                    1
                    for loc in file_meta.shard_locations
                    if loc.node_id in online_ids
                )
                if available_shards < file_meta.data_shards:
                    await self._store.mark_degraded(file_meta.file_id)
                    logger.error(
                        "DSS file %s degraded — only %d/%d shards reachable",
                        file_meta.file_id,
                        available_shards,
                        file_meta.data_shards,
                    )
