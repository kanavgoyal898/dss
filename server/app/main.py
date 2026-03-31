"""
Purpose: DSS Coordinator FastAPI application factory and entry point.
Responsibilities:
    - Instantiate all services and attach them to application state on startup.
    - Register the central API router with CORS configured for all local origins.
    - Start and stop the HealthMonitor background task via lifespan events.
    - Accept both the old and new origins so the UI works in dev and production.
Dependencies: fastapi, uvicorn, dss.server.app.api, dss.server.app.core.config,
              dss.server.app.services.*
"""

import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from dss.server.app.api import api_router
from dss.server.app.core.config import get_settings
from dss.server.app.services.health_monitor import HealthMonitor
from dss.server.app.services.metadata_store import MetadataStore
from dss.server.app.services.network_policy import NetworkPolicy
from dss.server.app.services.peer_registry import PeerRegistry
from dss.server.app.services.shard_mapper import ShardMapper

logger = logging.getLogger("dss.coordinator")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise DSS Coordinator services on startup; clean up on shutdown."""
    settings = get_settings()

    peer_registry = PeerRegistry(settings)
    metadata_store = MetadataStore()
    shard_mapper = ShardMapper(peer_registry)
    health_monitor = HealthMonitor(peer_registry, metadata_store, settings)
    network_policy = NetworkPolicy(
        mode=settings.network_mode,
        allowed_ips=list(settings.allowed_ips),
    )

    app.state.peer_registry = peer_registry
    app.state.metadata_store = metadata_store
    app.state.shard_mapper = shard_mapper
    app.state.health_monitor = health_monitor
    app.state.network_policy = network_policy

    await health_monitor.start()
    logger.info("DSS Coordinator ready on port %s", settings.port)
    yield
    await health_monitor.stop()


def create_app() -> FastAPI:
    """Construct and configure the DSS Coordinator FastAPI application."""
    app = FastAPI(
        title="DSS Coordinator",
        description="DSS (Distributed Storage System) coordinator API",
        version="1.0.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router)
    return app


app = create_app()


if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(
        "dss.server.app.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
        log_level="info",
    )
