"""Abstract base class for agent communication transports."""

from abc import ABC, abstractmethod


class AbstractTransport(ABC):
    """
    Abstract base for agent communication transports.

    Implementations can use WebSockets, Twilio, or other protocols
    while maintaining a consistent interface for the AgentBridge.
    """

    @abstractmethod
    async def connect(self) -> bool:
        """
        Establish connection to the agent.

        Returns:
            True if connection was successful, False otherwise.
        """
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """Close the connection to the agent."""
        ...

    @abstractmethod
    async def send(self, data: bytes) -> None:
        """
        Send data to the agent.

        Args:
            data: Raw bytes to send.
        """
        ...

    @abstractmethod
    async def receive(self, timeout: float = 1.0) -> bytes | str | None:
        """
        Receive data from the agent.

        Args:
            timeout: Maximum time to wait for data in seconds.

        Returns:
            Received bytes/string, or None if timeout occurred.
        """
        ...

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Check if the transport is currently connected."""
        ...

    @abstractmethod
    async def wait_for_start(self, timeout: float = 10.0) -> bool:
        """
        Wait until the media stream has started.

        Args:
            timeout: Maximum time to wait in seconds.

        Returns:
            True if started within timeout, False otherwise.
        """
        ...
