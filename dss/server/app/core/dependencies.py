"""
Purpose: FastAPI dependency providers for DSS Coordinator services.
Responsibilities:
    - Expose singleton service instances as FastAPI injectable dependencies.
    - Decouple route handlers from direct service instantiation.
Dependencies: fastapi, dss.server.app.services.*
"""

from functools import lru_cache

from fastapi import Request

from dss.server.app.services.health_monitor import HealthMonitor
from dss.server.app.services.metadata_store import MetadataStore
from dss.server.app.services.network_policy import NetworkPolicy
from dss.server.app.services.peer_registry import PeerRegistry
from dss.server.app.services.shard_mapper import ShardMapper


def get_peer_registry(request: Request) -> PeerRegistry:
    """Return the PeerRegistry instance attached to the application state."""
    return request.app.state.peer_registry


def get_metadata_store(request: Request) -> MetadataStore:
    """Return the MetadataStore instance attached to the application state."""
    return request.app.state.metadata_store


def get_shard_mapper(request: Request) -> ShardMapper:
    """Return the ShardMapper instance attached to the application state."""
    return request.app.state.shard_mapper


def get_health_monitor(request: Request) -> HealthMonitor:
    """Return the HealthMonitor instance attached to the application state."""
    return request.app.state.health_monitor


def get_network_policy(request: Request) -> NetworkPolicy:
    """Return the NetworkPolicy instance attached to the application state."""
    return request.app.state.network_policy
