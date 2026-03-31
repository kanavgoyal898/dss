"""
Purpose: DSS Peer Node background heartbeat sender with auto-reconnect.
Responsibilities:
    - Periodically POST heartbeat to the coordinator with current disk usage.
    - Attempt re-registration if heartbeat fails (token expired or coordinator restarted).
    - Stop cleanly when the application shuts down.
Dependencies: asyncio, logging, dss.client.app.services.coordinator_client,
              dss.client.app.storage.shard_store, dss.shared.schemas.peer
"""

import asyncio
import logging

from dss.client.app.services.coordinator_client import CoordinatorClient
from dss.client.app.storage.shard_store import ShardStore
from dss.shared.schemas.peer import HeartbeatRequest, PeerRegistration

logger = logging.getLogger("dss.heartbeat")


class HeartbeatService:
    """Sends periodic heartbeats from the peer node to the DSS Coordinator."""

    def __init__(
        self,
        node_id: str,
        coordinator: CoordinatorClient,
        shard_store: ShardStore,
        registration: PeerRegistration,
        interval_seconds: int = 15,
    ) -> None:
        """Initialise the heartbeat service with identity and service dependencies."""
        self._node_id = node_id
        self._coordinator = coordinator
        self._store = shard_store
        self._registration = registration
        self._interval = interval_seconds
        self._task: asyncio.Task = None
        self._running = False
        self._consecutive_failures = 0

    async def start(self) -> None:
        """Start the background heartbeat loop."""
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("DSS heartbeat started (interval=%ds)", self._interval)

    async def stop(self) -> None:
        """Cancel the background heartbeat task gracefully."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _loop(self) -> None:
        """Periodic coroutine: send heartbeat and attempt re-registration on failure."""
        while self._running:
            await asyncio.sleep(self._interval)
            try:
                used = self._store.total_used_bytes()
                ok = await self._coordinator.heartbeat(HeartbeatRequest(node_id=self._node_id, used_bytes=used))
                if ok:
                    self._consecutive_failures = 0
                    logger.debug("DSS heartbeat sent: used=%d bytes", used)
                else:
                    self._consecutive_failures += 1
                    if self._consecutive_failures >= 2 and self._coordinator.base_url:
                        logger.info("DSS attempting re-registration after %d heartbeat failures", self._consecutive_failures)
                        try:
                            await self._coordinator.register(self._registration)
                            self._consecutive_failures = 0
                        except Exception as exc:
                            logger.warning("DSS re-registration failed: %s", exc)
            except Exception as exc:
                self._consecutive_failures += 1
                logger.warning("DSS heartbeat error: %s", exc)
