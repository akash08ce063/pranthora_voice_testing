"""FastAPI application for Agent Bridge service."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.routes import websocket, twilio


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Cleanup on shutdown."""
    yield
    # Stop all WebSocket bridges
    for bridge in list(websocket.active_bridges.values()):
        await bridge.stop()
    websocket.active_bridges.clear()

    # Stop all Twilio bridges
    for session_id in list(twilio.active_bridges.keys()):
        await twilio._stop_session(session_id)
    twilio.active_bridges.clear()


app = FastAPI(
    title="Agent Bridge Service",
    description="Enables two voice agents to have real-time conversations",
    version="1.0.0",
    lifespan=lifespan,
)

# Include routers
app.include_router(websocket.router)
app.include_router(twilio.router)


@app.get("/health", tags=["Health"])
async def health():
    """Health check."""
    return {
        "status": "healthy",
        "websocket_sessions": len(websocket.active_bridges),
        "twilio_sessions": len(twilio.active_bridges),
    }

