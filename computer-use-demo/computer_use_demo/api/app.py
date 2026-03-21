"""FastAPI application entry point.

Sets up the app with CORS, lifespan events, route registration,
and static file serving for the frontend and noVNC.
"""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from . import database as db
from .display_manager import display_manager
from .session_manager import session_manager
from .routes import sessions, agent, vm, files

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """App lifespan: init DB and cleanup on shutdown."""
    # Startup
    logger.info("Starting Computer Use API...")

    # Ensure data directory exists
    os.makedirs("/data", exist_ok=True)

    await db.init_db()
    logger.info("Database initialized")

    yield

    # Shutdown
    logger.info("Shutting down...")
    await session_manager.shutdown()
    await display_manager.release_all()
    await db.close_db()
    logger.info("Shutdown complete")


app = FastAPI(
    title="Computer Use API",
    description="Backend API for Claude Computer Use agent sessions with real-time streaming",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow all for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
    """Health check endpoint."""
    return {
        "status": "healthy",
        "active_sessions": display_manager.active_count,
    }
