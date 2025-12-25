"""FastAPI application for Agent Bridge service."""

from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI

from api.v1.routes import twilio, websocket
from utils.logger import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Cleanup on shutdown."""
    logger.info("Application startup")
    yield
    logger.info("Application shutdown - cleaning up bridges")
    # Stop all WebSocket bridges
    websocket_count = len(websocket.active_bridges)
    for bridge in list(websocket.active_bridges.values()):
        await bridge.stop()
    websocket.active_bridges.clear()
    logger.info(f"Stopped {websocket_count} WebSocket bridges")

    # Stop all Twilio bridges
    twilio_count = len(twilio.active_bridges)
    for session_id in list(twilio.active_bridges.keys()):
        await twilio._stop_session(session_id)
    twilio.active_bridges.clear()
    logger.info(f"Stopped {twilio_count} Twilio bridges")


app = FastAPI(
    title="Agent Bridge Service",
    description="Enables two voice agents to have real-time conversations",
    version="1.0.0",
    lifespan=lifespan,
)

# Create v1 API router
v1_router = APIRouter(prefix="/v1")

# Include routers under v1
v1_router.include_router(websocket.router)
v1_router.include_router(twilio.router)

# Include v1 router in main app
app.include_router(v1_router)


@app.get("/health", tags=["Health"])
async def health():
    """Health check."""
    return {
        "status": "healthy",
        "websocket_sessions": len(websocket.active_bridges),
        "twilio_sessions": len(twilio.active_bridges),
    }
