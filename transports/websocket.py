"""WebSocket transport implementation for agent communication."""

import asyncio
import logging

import websockets
from websockets.asyncio.client import ClientConnection

from transports.base import AbstractTransport

logger = logging.getLogger(__name__)


class WebSocketTransport(AbstractTransport):
    """
    WebSocket-based transport for connecting to voice agents.

    Connects to a backend WebSocket URL and handles bidirectional
    communication with a single agent.
    """

    def __init__(self, ws_url: str, agent_id: str):
        """
        Initialize the WebSocket transport.

        Args:
            ws_url: Base WebSocket URL of the voice backend.
            agent_id: ID of the agent to connect to.
        """
        self._ws_url = ws_url.rstrip("/")
        self._agent_id = agent_id
        self._websocket: ClientConnection | None = None
        self._connected = False
        self._started = False

    def _build_url(self) -> str:
        """Build the full WebSocket URL for the agent."""
        return f"{self._ws_url}/api/call/web-media-stream?agent_id={self._agent_id}"

    async def connect(self) -> bool:
        """Connect to the agent's WebSocket endpoint."""
        try:
            url = self._build_url()
            logger.info(f"Connecting to agent {self._agent_id} at {url}")

            self._websocket = await websockets.connect(url)
            self._connected = True
            self._started = True  # WebSocket is ready immediately after connection

            logger.info(f"Successfully connected to agent {self._agent_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to agent {self._agent_id}: {e}")
            self._connected = False
            self._started = False
            return False

    async def disconnect(self) -> None:
        """Close the WebSocket connection."""
        if self._websocket:
            try:
                await self._websocket.close()
                logger.info(f"Disconnected from agent {self._agent_id}")
            except Exception as e:
                logger.warning(f"Error closing connection to {self._agent_id}: {e}")
            finally:
                self._websocket = None
                self._connected = False
                self._started = False

    async def send(self, data: bytes) -> None:
        """Send data through the WebSocket."""
        if self._websocket and self._connected:
            await self._websocket.send(data)

    async def receive(self, timeout: float = 1.0) -> bytes | str | None:
        """
        Receive data from the WebSocket.

        Returns:
            bytes or str if data received, None on timeout.
        """
        if not self._websocket or not self._connected:
            return None

        try:
            message = await asyncio.wait_for(self._websocket.recv(), timeout=timeout)
            return message
        except asyncio.TimeoutError:
            return None
        except websockets.exceptions.ConnectionClosed:
            self._connected = False
            raise

    @property
    def is_connected(self) -> bool:
        """Check if the WebSocket is connected."""
        return self._connected

    @property
    def agent_id(self) -> str:
        """Get the agent ID for this transport."""
        return self._agent_id

    async def wait_for_start(self, timeout: float = 10.0) -> bool:
        """
        Wait until the media stream has started.

        For WebSocket transport, this is immediately ready after connection.

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
