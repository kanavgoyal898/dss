"""
Purpose: DSS Peer Node FastAPI application factory and entry point.
Responsibilities:
    - Load or generate node identity on startup.
    - Attempt coordinator registration; log gracefully if unavailable.
    - Wire up all services and attach them to application state.
    - Start and stop the HeartbeatService background task via lifespan events.
Dependencies: fastapi, uvicorn, dss.client.app.core.*, dss.client.app.services.*,
              dss.client.app.storage.shard_store
"""

import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from dss.client.app.api.routes.node import router as node_router
from dss.client.app.api.routes.shards import router as shards_router
from dss.client.app.core.config import get_settings
from dss.client.app.core.identity import load_or_create_identity
from dss.client.app.services.coordinator_client import CoordinatorClient
from dss.client.app.services.download_pipeline import DownloadPipeline
from dss.client.app.services.heartbeat_service import HeartbeatService
from dss.client.app.services.upload_pipeline import UploadPipeline
from dss.client.app.storage.shard_store import ShardStore
from dss.shared.schemas.peer import PeerRegistration

logger = logging.getLogger("dss.node")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise DSS Peer Node services on startup; clean up on shutdown."""
    settings = get_settings()
    identity = load_or_create_identity(settings.identity_dir)
    shard_store = ShardStore(settings.storage_dir)
    coordinator = CoordinatorClient(settings.coordinator_url)

    registration = PeerRegistration(
        node_id=identity.node_id,
        public_key_pem=identity.public_key_pem,
        host=settings.get_advertised_host(),
        port=settings.get_port(),
        capacity_bytes=settings.capacity_bytes,
    )

    try:
        await coordinator.register(registration)
        logger.info("DSS Node started and registered: node_id=%s", identity.node_id)
    except Exception as exc:
        logger.warning(
            "DSS Node started without coordinator (%s). Use the dashboard to connect.", exc
        )

    upload_pipeline = UploadPipeline(
        coordinator=coordinator,
        identity=identity,
        data_shards=settings.data_shards,
        total_shards=settings.total_shards,
        chunk_size=settings.chunk_size_bytes,
    )
    download_pipeline = DownloadPipeline(coordinator=coordinator, identity=identity)
    heartbeat_service = HeartbeatService(
        node_id=identity.node_id,
        coordinator=coordinator,
        shard_store=shard_store,
        registration=registration,
        interval_seconds=settings.heartbeat_interval_seconds,
    )

    app.state.settings = settings
    app.state.identity = identity
    app.state.shard_store = shard_store
    app.state.coordinator = coordinator
    app.state.registration = registration
    app.state.upload_pipeline = upload_pipeline
    app.state.download_pipeline = download_pipeline

    await heartbeat_service.start()
    yield
    await heartbeat_service.stop()
    await coordinator.close()


def create_app() -> FastAPI:
    """Construct and configure the DSS Peer Node FastAPI application."""
    app = FastAPI(
        title="DSS Node",
        description="DSS (Distributed Storage System) peer node API",
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
    app.include_router(shards_router)
    app.include_router(node_router)
    return app


app = create_app()


if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(
        "dss.client.app.main:app",
        host=settings.host,
        port=settings.get_port(),
        reload=False,
        log_level="info",
    )
