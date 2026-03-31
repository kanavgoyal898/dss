"""
Purpose: Package marker and central API router for dss.client.app.api.
Responsibilities: Aggregate shard and node routers.
Dependencies: fastapi, dss.client.app.api.routes.*
"""
from fastapi import APIRouter
from dss.client.app.api.routes.shards import router as shards_router
from dss.client.app.api.routes.node import router as node_router
api_router = APIRouter()
api_router.include_router(shards_router)
api_router.include_router(node_router)
