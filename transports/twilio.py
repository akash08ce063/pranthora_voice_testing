"""Twilio transport implementation for agent-to-agent communication."""

import asyncio
import json
import logging
from collections import deque
from typing import Optional

from transports.base import AbstractTransport

logger = logging.getLogger(__name__)


class TwilioTransport(AbstractTransport):
    """
    Twilio-based transport for connecting voice agents via phone calls.

    This transport handles Twilio Media Streams, receiving and sending
    audio in mulaw format. It's designed to work with Twilio's WebSocket
    media streaming protocol.

    The transport expects to receive messages in Twilio's Media Stream format:
    {
        "event": "media" | "start" | "stop",
        "streamSid": "...",
        "media": {"payload": "base64-encoded-audio"}
    }
    """

    def __init__(
        self,
        agent_id: str,
        phone_number: str,
        call_sid: Optional[str] = None,
    ):
        """
        Initialize the Twilio transport.

        Args:
            agent_id: ID of the agent (for logging and identification).
            phone_number: Phone number of the agent to call.
            call_sid: Twilio Call SID (set after call is initiated).
        """
        self._agent_id = agent_id
        self._phone_number = phone_number
        self._call_sid = call_sid
        self._stream_sid: Optional[str] = None
        self._connected = False
        self._websocket = None  # Will be set externally by the bridge
        self._receive_queue: deque = deque()
        self._started = False

    @property
    def agent_id(self) -> str:
        """Get the agent ID."""
        return self._agent_id

    @property
    def phone_number(self) -> str:
        """Get the phone number."""
        return self._phone_number

    @property
    def call_sid(self) -> Optional[str]:
        """Get the Twilio Call SID."""
        return self._call_sid

    @call_sid.setter
    def call_sid(self, value: str) -> None:
        """Set the Twilio Call SID."""
        self._call_sid = value

    @property
    def stream_sid(self) -> Optional[str]:
        """Get the Twilio Stream SID."""
        return self._stream_sid

    def set_websocket(self, websocket) -> None:
        """
        Set the WebSocket connection for this transport.

        This is called externally when Twilio establishes the media stream
        WebSocket connection.

        Args:
            websocket: The WebSocket connection object.
        """
        self._websocket = websocket
        logger.info(f"WebSocket set for agent {self._agent_id}")

    async def connect(self) -> bool:
        """
        Mark the transport as ready to connect.

        For Twilio, the actual connection is established when:
        1. The call is initiated (via Twilio REST API)
        2. The media stream WebSocket is connected (via webhook)

        Returns:
            True if ready to connect.
        """
        logger.info(f"Twilio transport for agent {self._agent_id} ready (call will be initiated externally)")
        self._connected = True
        return True

    async def disconnect(self) -> None:
        """
        Disconnect the Twilio transport.

        This closes the WebSocket connection and marks the transport as disconnected.
        The actual call termination should be handled externally via Twilio REST API.
        """
        if self._websocket:
            try:
                await self._websocket.close()
                logger.info(f"Closed WebSocket for agent {self._agent_id}")
            except Exception as e:
                logger.warning(f"Error closing WebSocket for agent {self._agent_id}: {e}")
            finally:
                self._websocket = None

        self._connected = False
        self._started = False
        logger.info(f"Twilio transport disconnected for agent {self._agent_id}")

    async def send(self, data: bytes) -> None:
        """
        Send audio data through the Twilio media stream.

        Args:
            data: Raw audio bytes (assumed to be mulaw PCM).
        """
        if not self._websocket or not self._connected or not self._started:
            logger.warning(f"Cannot send - agent {self._agent_id} not ready")
            return

        if not self._stream_sid:
            logger.warning(f"Cannot send - no stream SID for agent {self._agent_id}")
            return

        try:
            # Twilio expects base64-encoded mulaw audio
            import base64

            payload = base64.b64encode(data).decode("utf-8")

            message = {"event": "media", "streamSid": self._stream_sid, "media": {"payload": payload}}

            await self._websocket.send(json.dumps(message))

        except Exception as e:
            logger.error(f"Error sending data for agent {self._agent_id}: {e}")

    async def receive(self, timeout: float = 1.0) -> bytes | str | None:
        """
        Receive data from the Twilio media stream.

        Args:
            timeout: Maximum time to wait for data in seconds.

        Returns:
            bytes (decoded audio), str (control message), or None on timeout.
        """
        if not self._websocket or not self._connected:
            return None

        # Check if we have queued messages first
        if self._receive_queue:
            return self._receive_queue.popleft()

        try:
            message = await asyncio.wait_for(self._websocket.recv(), timeout=timeout)

            return await self._process_message(message)

        except asyncio.TimeoutError:
            return None
        except Exception as e:
            logger.error(f"Error receiving from agent {self._agent_id}: {e}")
            self._connected = False
            raise

    async def _process_message(self, message: str) -> bytes | str | None:
        """
        Process incoming Twilio media stream message.

        Args:
            message: Raw JSON message from Twilio.

        Returns:
            Decoded audio bytes, control message string, or None.
        """
        try:
            data = json.loads(message)
            event = data.get("event")

            if event == "start":
                # Media stream started
                self._stream_sid = data.get("streamSid")
                self._started = True
                logger.info(f"Media stream started for agent {self._agent_id} (streamSid: {self._stream_sid})")

                # Return a control message
                return json.dumps({"event_type": "start_media_streaming", "agent_id": self._agent_id, "stream_sid": self._stream_sid})

            elif event == "media":
                # Audio data received
                if not self._started:
                    logger.warning(f"Received media before stream started for agent {self._agent_id}")
                    return None

                payload = data.get("media", {}).get("payload")
                if payload:
                    # Decode base64 mulaw audio
                    import base64

                    audio_bytes = base64.b64decode(payload)
                    return audio_bytes

                return None

            elif event == "stop":
                # Media stream stopped
                logger.info(f"Media stream stopped for agent {self._agent_id}")
                self._started = False
                return json.dumps({"event_type": "stop_media_streaming", "agent_id": self._agent_id})

            elif event == "mark":
                # Mark event (can be used for synchronization)
                logger.debug(f"Mark event received for agent {self._agent_id}")
                return None

            else:
                logger.warning(f"Unknown event type '{event}' from agent {self._agent_id}")
                return None

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON message from agent {self._agent_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error processing message for agent {self._agent_id}: {e}")
            return None

    def queue_message(self, data: bytes | str) -> None:
        """
        Queue a message for later retrieval via receive().

        This is useful when messages are received externally (e.g., from a
        WebSocket handler) and need to be processed by the bridge.

        Args:
            data: Audio bytes or control message string.
        """
        self._receive_queue.append(data)

    @property
    def is_connected(self) -> bool:
        """Check if the transport is connected."""
        return self._connected and self._websocket is not None

    @property
    def is_started(self) -> bool:
        """Check if the media stream has started."""
        return self._started

    async def wait_for_start(self, timeout: float = 10.0) -> bool:
        """
        Wait until the media stream has started.

        Args:
            timeout: Maximum time to wait in seconds.

        Returns:
            True if started within timeout, False otherwise.
        """
        start_time = asyncio.get_event_loop().time()
        while not self._started:
            if asyncio.get_event_loop().time() - start_time > timeout:
                logger.warning(f"Timeout waiting for stream start on agent {self._agent_id}")
                return False
            await asyncio.sleep(0.1)
        logger.info(f"Stream started for agent {self._agent_id}")
        return True
