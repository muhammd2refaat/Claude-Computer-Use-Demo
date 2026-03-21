"""FastAPI application entry point.

Sets up the app with CORS, lifespan events, route registration,
and static file serving for the frontend and noVNC.
"""

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from computer_use_demo.config.settings import settings
from computer_use_demo import db
from computer_use_demo.services.display import display_service
from computer_use_demo.services.session import session_service
from computer_use_demo.utils.logger import setup_logger
from .routes import sessions, agent, vm, files

logger = setup_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """App lifespan: init DB and cleanup on shutdown."""
    # Startup
    logger.info("Starting Computer Use API...")

    # Ensure data directory exists
    os.makedirs("/data", exist_ok=True)

    await db.init_db()
    pool_stats = db.get_pool_stats()
    if pool_stats:
        logger.info(
            f"Database connection pool initialized: "
            f"size={pool_stats.get('pool_size', 0)}, max={pool_stats.get('max_size', 10)}"
        )

    yield

    # Shutdown
    logger.info("Shutting down...")
    await session_service.shutdown()
    await display_service.release_all()
    await db.close_db()
    logger.info("Shutdown complete")


app = FastAPI(
    title=settings.APP_NAME,
    description="Backend API for Claude Computer Use agent sessions with real-time streaming",
    version=settings.API_VERSION,
    lifespan=lifespan,
)

# CORS — allow all for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routes
app.include_router(sessions.router)
app.include_router(agent.router)
app.include_router(vm.router)
app.include_router(files.router)

# Mount noVNC static files (served from Docker image)
novnc_path = Path("/opt/noVNC")
if novnc_path.exists():
    app.mount("/vnc", StaticFiles(directory=str(novnc_path), html=True), name="novnc")

# Mount frontend static files
frontend_path = Path(__file__).resolve().parent.parent.parent / "frontend"
if frontend_path.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_path)), name="frontend")


@app.get("/")
async def root():
    """Serve the frontend index.html."""
    index_path = frontend_path / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"message": "Computer Use API", "docs": "/docs"}


@app.get("/test")
async def concurrent_test():
    """Serve the concurrent sessions test page."""
    test_path = frontend_path / "concurrent_test.html"
    if test_path.exists():
        return FileResponse(str(test_path))
    return {"message": "Test page not found", "note": "Create frontend/concurrent_test.html"}


@app.get("/health")
async def health():
    """Health check endpoint with connection pool statistics."""
    pool_stats = db.get_pool_stats()

    return {
        "status": "healthy",
        "active_sessions": display_service.active_count,
        "database": {
            "pool_size": pool_stats.get("pool_size", 0) if pool_stats else 0,
            "available": pool_stats.get("available", 0) if pool_stats else 0,
            "in_use": pool_stats.get("in_use", 0) if pool_stats else 0,
            "max_size": pool_stats.get("max_size", 10) if pool_stats else 10,
            "total_acquired": pool_stats.get("acquired", 0) if pool_stats else 0,
            "health_checks": pool_stats.get("health_checks", 0) if pool_stats else 0,
        } if pool_stats else None,
    }
