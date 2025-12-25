"""
Bridge-related data models.

This module contains data classes and enums used by the bridge implementations.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from transports.base import AbstractTransport


class BridgeStatus(str, Enum):
    """Status of a bridge connection."""

    IDLE = "idle"
    CONNECTING = "connecting"
    ACTIVE = "active"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class ConversationStats:
    """Statistics for an agent-to-agent conversation."""

    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    agent_a_bytes_sent: int = 0
    agent_b_bytes_sent: int = 0
    agent_a_messages: int = 0
    agent_b_messages: int = 0
    first_audio_at: Optional[datetime] = None
    time_to_first_audio: Optional[float] = None

    @property
    def total_bytes(self) -> int:
        """Total bytes transferred in both directions."""
        return self.agent_a_bytes_sent + self.agent_b_bytes_sent

    @property
    def duration_seconds(self) -> Optional[float]:
        """Total conversation duration in seconds."""
        if self.started_at:
            end_time = self.ended_at or datetime.now()
            return (end_time - self.started_at).total_seconds()
        return None


@dataclass
class AgentConnection:
    """Represents a connection to a single agent via a transport."""

    agent_id: str
    transport: AbstractTransport
    buffered_message: Optional[bytes] = field(default=None)

    @property
    def is_connected(self) -> bool:
        return self.transport.is_connected
