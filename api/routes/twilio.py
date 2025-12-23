"""Twilio-based conversation routes."""

import asyncio
import logging
import os
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from pydantic import BaseModel, Field

from bridge import AgentBridge, BridgeStatus
from transports.twilio import TwilioTransport

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/twilio", tags=["Twilio Conversations"])

# Store active bridges and transports
active_bridges: dict[str, AgentBridge] = {}
twilio_transports: dict[str, TwilioTransport] = {}  # "session-agent" -> transport
twilio_call_sids: dict[str, dict] = {}  # session -> {"a": sid, "b": sid}

# Twilio client (lazy init)
_twilio_client = None


def _get_twilio_client():
    """Get or create Twilio client."""
    global _twilio_client
    if _twilio_client is None:
        account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        if account_sid and auth_token:
            from twilio.rest import Client
            _twilio_client = Client(account_sid, auth_token)
    return _twilio_client


def _create_twilio_transport(session_id: str, agent_type: str):
    """Factory to create and store Twilio transports."""
    def factory(phone_number: str, agent_id: str) -> TwilioTransport:
        transport = TwilioTransport(agent_id=agent_id, phone_number=phone_number)
        twilio_transports[f"{session_id}-{agent_type}"] = transport
        return transport
    return factory


class StartCallRequest(BaseModel):
    agent_a_number: str = Field(..., description="Phone number of agent A (E.164 format)")
    agent_b_number: str = Field(..., description="Phone number of agent B (E.164 format)")
    agent_a_id: str = Field("agent_a", description="ID for agent A")
    agent_b_id: str = Field("agent_b", description="ID for agent B")
    session_id: Optional[str] = Field(None)
    max_duration_seconds: Optional[int] = Field(None, gt=0)
    recording_enabled: bool = Field(True)
    recording_path: str = Field("recordings")


class StartCallResponse(BaseModel):
    success: bool
    session_id: str
    call_sid_a: Optional[str] = None
    call_sid_b: Optional[str] = None
    message: str


@router.post("/calls", response_model=StartCallResponse)
async def start_call(request: StartCallRequest):
    """Start a Twilio-based agent-to-agent call."""
    client = _get_twilio_client()
    twilio_number = os.getenv("TWILIO_PHONE_NUMBER")
    webhook_base = os.getenv("TWILIO_WEBHOOK_BASE_URL")

    if not client or not twilio_number or not webhook_base:
        raise HTTPException(
            status_code=503,
            detail="Twilio not configured. Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER, TWILIO_WEBHOOK_BASE_URL",
        )

    session_id = request.session_id or f"twilio-{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    if session_id in active_bridges:
        raise HTTPException(status_code=409, detail=f"Session '{session_id}' already exists")

    try:
        # Initiate calls to both agents
        call_a = client.calls.create(
            to=request.agent_a_number,
            from_=twilio_number,
            url=f"{webhook_base}/twilio/twiml?session={session_id}&agent=a",
            status_callback=f"{webhook_base}/twilio/status?session={session_id}&agent=a",
            status_callback_event=["completed"],
        )

        call_b = client.calls.create(
            to=request.agent_b_number,
            from_=twilio_number,
            url=f"{webhook_base}/twilio/twiml?session={session_id}&agent=b",
            status_callback=f"{webhook_base}/twilio/status?session={session_id}&agent=b",
            status_callback_event=["completed"],
        )

        # Store call SIDs
        twilio_call_sids[session_id] = {"a": call_a.sid, "b": call_b.sid}

        # Create bridge with Twilio transports
        bridge = AgentBridge(
            transport_factory=lambda url, aid: _create_twilio_transport(
                session_id, "a" if aid == request.agent_a_id else "b"
            )(url, aid),
            backend_url=request.agent_a_number,
            agent_a_id=request.agent_a_id,
            agent_b_id=request.agent_b_id,
            conversation_id=session_id,
            max_duration_seconds=request.max_duration_seconds,
            recording_enabled=request.recording_enabled,
            recording_path=request.recording_path,
        )

        # Store call SIDs in transports
        if t := twilio_transports.get(f"{session_id}-a"):
            t.call_sid = call_a.sid
        if t := twilio_transports.get(f"{session_id}-b"):
            t.call_sid = call_b.sid

        active_bridges[session_id] = bridge

        return StartCallResponse(
            success=True,
            session_id=session_id,
            call_sid_a=call_a.sid,
            call_sid_b=call_b.sid,
            message="Calls initiated. Waiting for agents to answer.",
        )

    except Exception as e:
        logger.error(f"Error initiating calls: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/twiml")
async def twiml_webhook(session: str, agent: str):
    """Return TwiML to connect call to media stream."""
    webhook_base = os.getenv("TWILIO_WEBHOOK_BASE_URL")
    if not webhook_base:
        raise HTTPException(status_code=503, detail="Twilio not configured")

    from twilio.twiml.voice_response import Connect, VoiceResponse

    response = VoiceResponse()
    connect = Connect()
    connect.stream(url=f"{webhook_base}/twilio/stream?session={session}&agent={agent}")
    response.append(connect)

    return Response(content=str(response), media_type="application/xml")


@router.websocket("/stream")
async def media_stream(websocket: WebSocket, session: str, agent: str):
    """Handle Twilio media stream WebSocket."""
    key = f"{session}-{agent}"
    transport = twilio_transports.get(key)

    if not transport:
        await websocket.close(code=1011, reason="Transport not found")
        return

    await websocket.accept()
    transport.set_websocket(websocket)
    logger.info(f"WebSocket connected: {key}")

    # Check if both transports connected -> start bridge
    other = "b" if agent == "a" else "a"
    other_transport = twilio_transports.get(f"{session}-{other}")

    if other_transport and other_transport.is_connected:
        bridge = active_bridges.get(session)
        if bridge and bridge.status == BridgeStatus.IDLE:
            logger.info(f"Both agents connected, starting bridge: {session}")
            asyncio.create_task(_run_bridge(bridge))

    try:
        while True:
            message = await websocket.receive_text()
            result = await transport._process_message(message)
            if result is not None:
                transport.queue_message(result)
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {key}")
    except Exception as e:
        logger.error(f"WebSocket error {key}: {e}")
    finally:
        await transport.disconnect()


async def _run_bridge(bridge: AgentBridge):
    """Start and run bridge until completion."""
    try:
        if await bridge.start():
            await asyncio.gather(*bridge._tasks, return_exceptions=True)
    finally:
        await bridge.stop()


@router.post("/status")
async def status_callback(request: Request, session: str, agent: str):
    """Handle Twilio call status updates."""
    form = await request.form()
    status = form.get("CallStatus")
    logger.info(f"Call status: session={session}, agent={agent}, status={status}")

    if status == "completed":
        bridge = active_bridges.get(session)
        if bridge and bridge.status == BridgeStatus.ACTIVE:
            asyncio.create_task(_stop_session(session))

    return {"status": "ok"}


async def _stop_session(session_id: str):
    """Stop session and end calls."""
    client = _get_twilio_client()
    bridge = active_bridges.get(session_id)

    if bridge:
        await bridge.stop()

    # End Twilio calls
    if client and (sids := twilio_call_sids.get(session_id)):
        for sid in sids.values():
            try:
                client.calls(sid).update(status="completed")
            except Exception as e:
                logger.error(f"Error ending call {sid}: {e}")

    # Cleanup
    twilio_call_sids.pop(session_id, None)
    twilio_transports.pop(f"{session_id}-a", None)
    twilio_transports.pop(f"{session_id}-b", None)


@router.post("/calls/{session_id}/stop")
async def stop_call(session_id: str):
    """Stop a Twilio call session."""
    if session_id not in active_bridges:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    await _stop_session(session_id)
    return {"success": True, "session_id": session_id, "message": "Session stopped"}


@router.get("/calls/{session_id}")
async def get_call_status(session_id: str):
    """Get call session status."""
    bridge = active_bridges.get(session_id)
    if not bridge:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    status = bridge.get_status()
    status["call_sids"] = twilio_call_sids.get(session_id, {})
    return status


@router.get("/calls")
async def list_calls():
    """List all Twilio call sessions."""
    return {
        "total": len(active_bridges),
        "sessions": [b.get_status() for b in active_bridges.values()],
    }

