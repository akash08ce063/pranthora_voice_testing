"""WebSocket-based conversation routes."""

import asyncio
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from bridge import AgentBridge, BridgeStatus
from transports.websocket import WebSocketTransport

router = APIRouter(prefix="/conversations", tags=["WebSocket Conversations"])

# Store active bridges
active_bridges: dict[str, AgentBridge] = {}


class StartConversationRequest(BaseModel):
    backend_ws_url: str = Field(..., description="WebSocket URL of the voice backend")
    agent_a_id: str = Field(..., description="ID of the first agent")
    agent_b_id: str = Field(..., description="ID of the second agent")
    conversation_id: Optional[str] = Field(None, description="Optional custom conversation ID")
    max_duration_seconds: Optional[int] = Field(None, gt=0)
    recording_enabled: bool = Field(True)
    recording_path: str = Field("recordings")


class ConversationResponse(BaseModel):
    success: bool
    conversation_id: str
    message: str
    status: dict


def _create_websocket_transport(backend_url: str, agent_id: str) -> WebSocketTransport:
    """Create a WebSocket transport for an agent."""
    return WebSocketTransport(ws_url=backend_url, agent_id=agent_id)


@router.post("", response_model=ConversationResponse)
async def start_conversation(request: StartConversationRequest):
    """Start a new WebSocket-based agent-to-agent conversation."""
    bridge = AgentBridge(
        transport_factory=_create_websocket_transport,
        backend_url=request.backend_ws_url,
        agent_a_id=request.agent_a_id,
        agent_b_id=request.agent_b_id,
        conversation_id=request.conversation_id,
        max_duration_seconds=request.max_duration_seconds,
        recording_enabled=request.recording_enabled,
        recording_path=request.recording_path,
    )

    if bridge.conversation_id in active_bridges:
        raise HTTPException(status_code=409, detail=f"Conversation '{bridge.conversation_id}' already exists")

    success = await bridge.start()
    if not success:
        raise HTTPException(status_code=500, detail="Failed to start conversation")

    active_bridges[bridge.conversation_id] = bridge
    asyncio.create_task(_run_bridge(bridge))

    return ConversationResponse(
        success=True,
        conversation_id=bridge.conversation_id,
        message="Conversation started",
        status=bridge.get_status(),
    )


async def _run_bridge(bridge: AgentBridge):
    """Run bridge until completion."""
    try:
        await asyncio.gather(*bridge._tasks, return_exceptions=True)
    finally:
        await bridge.stop()


@router.get("/{conversation_id}")
async def get_status(conversation_id: str):
    """Get conversation status."""
    bridge = active_bridges.get(conversation_id)
    if not bridge:
        raise HTTPException(status_code=404, detail=f"Conversation '{conversation_id}' not found")
    return bridge.get_status()


@router.post("/{conversation_id}/stop")
async def stop_conversation(conversation_id: str):
    """Stop a conversation."""
    bridge = active_bridges.get(conversation_id)
    if not bridge:
        raise HTTPException(status_code=404, detail=f"Conversation '{conversation_id}' not found")

    await bridge.stop()
    return {"success": True, "conversation_id": conversation_id, "status": bridge.get_status()}


@router.delete("/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """Delete a conversation."""
    bridge = active_bridges.get(conversation_id)
    if not bridge:
        raise HTTPException(status_code=404, detail=f"Conversation '{conversation_id}' not found")

    if bridge.status not in (BridgeStatus.STOPPED, BridgeStatus.ERROR):
        await bridge.stop()

    del active_bridges[conversation_id]
    return {"success": True, "message": f"Conversation '{conversation_id}' deleted"}


@router.get("")
async def list_conversations():
    """List all conversations."""
    return {
        "total": len(active_bridges),
        "conversations": [b.get_status() for b in active_bridges.values()],
    }
