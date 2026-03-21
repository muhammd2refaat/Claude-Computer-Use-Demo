"""
FastAPI Application Entry Point
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import sessions, agent
from app.api.websocket import stream
from app.config.settings import settings
from app.db.database import init_db
from app.utils.logger import setup_logger

logger = setup_logger(__name__)

app = FastAPI(
    title="AI Agent API",
    description="Claude-powered computer-use agent with streaming capabilities",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(sessions.router, prefix="/api", tags=["sessions"])
app.include_router(agent.router, prefix="/api/agent", tags=["agent"])
app.include_router(stream.router, prefix="/ws", tags=["websocket"])


@app.on_event("startup")
async def startup_event():
    """Initialize database and other resources on startup"""
    logger.info("Starting up AI Agent API...")
    await init_db()
    logger.info("Database initialized")


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on shutdown"""
    logger.info("Shutting down AI Agent API...")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "ai-agent-api"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
