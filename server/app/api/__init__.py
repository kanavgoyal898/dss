"""
Purpose: Central API router for the DSS Coordinator FastAPI application.
Responsibilities:
    - Aggregate all sub-routers (peers, files, admin) under a versioned /api/v1 prefix.
    - Provide a single import point for the application factory.
Dependencies: fastapi, dss.server.app.api.routes.*
"""

from fastapi import APIRouter

from dss.server.app.api.routes.admin import router as admin_router
from dss.server.app.api.routes.files import router as files_router
from dss.server.app.api.routes.peers import router as peers_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(peers_router)
api_router.include_router(files_router)
api_router.include_router(admin_router)
