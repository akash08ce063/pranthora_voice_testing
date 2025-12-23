"""
Audio recorder module for capturing agent-to-agent conversations.
"""

import logging
import wave
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Optional

logger = logging.getLogger(__name__)


class ConversationRecorder:
    """
    Records audio from an agent-to-agent conversation to a WAV file.

    This class handles thread-safe recording of audio chunks from multiple
    concurrent sources (Agent A and Agent B) into a single mixed audio file.
    """

    def __init__(
        self,
        conversation_id: str,
        recording_path: str = 'recordings',
        sample_rate: int = 16000,
        channels: int = 1,
        sample_width: int = 2,  # 16-bit = 2 bytes
    ):
        """
        Initialize the conversation recorder.

        Args:
            conversation_id: Unique identifier for the conversation
            recording_path: Directory to save recordings (default: "recordings/")
            sample_rate: Audio sample rate in Hz (default: 16000)
            channels: Number of audio channels (default: 1 for mono)
            sample_width: Sample width in bytes (default: 2 for 16-bit)
        """
        self.conversation_id = conversation_id
        self.sample_rate = sample_rate
        self.channels = channels
        self.sample_width = sample_width

        # Set up recording path
        self.recording_dir = Path(recording_path)

        # Create recording directory if it doesn't exist
        self.recording_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.filename = f"{conversation_id}_{timestamp}.wav"
        self.filepath = self.recording_dir / self.filename

        # Thread safety for concurrent writes
        self._lock = Lock()
        self._wav_file: Optional[wave.Wave_write] = None
        self._is_open = False

        logger.info(f"[{conversation_id}] Recorder initialized: {self.filepath}")

    def open(self) -> bool:
        """
        Open the WAV file for writing.

        Returns:
            True if file opened successfully, False otherwise
        """
        try:
            with self._lock:
                self._wav_file = wave.open(str(self.filepath), "wb")
                self._wav_file.setnchannels(self.channels)
                self._wav_file.setsampwidth(self.sample_width)
                self._wav_file.setframerate(self.sample_rate)
                self._is_open = True
                logger.info(f"[{self.conversation_id}] Recording started: {self.filepath}")
                return True
        except Exception as e:
            logger.error(f"[{self.conversation_id}] Failed to open recording file: {e}")
            return False

    def write_audio(self, audio_data: bytes) -> None:
        """
        Write audio data to the recording file.

        This method is thread-safe and can be called from multiple concurrent tasks.

        Args:
            audio_data: Raw PCM audio bytes to write
        """
        if not self._is_open or self._wav_file is None:
            logger.warning(f"[{self.conversation_id}] Attempted to write to closed recorder")
            return

        try:
            with self._lock:
                if self._wav_file is not None:
                    self._wav_file.writeframes(audio_data)
        except Exception as e:
            logger.error(f"[{self.conversation_id}] Error writing audio data: {e}")

    def close(self) -> None:
        """
        Close the WAV file and finalize the recording.
        """
        try:
            with self._lock:
                if self._wav_file is not None:
                    self._wav_file.close()
                    self._wav_file = None
                    self._is_open = False

                    # Log file size
                    if self.filepath.exists():
                        size_mb = self.filepath.stat().st_size / (1024 * 1024)
                        logger.info(f"[{self.conversation_id}] Recording saved: {self.filepath} ({size_mb:.2f} MB)")
        except Exception as e:
            logger.error(f"[{self.conversation_id}] Error closing recording file: {e}")

    def __enter__(self):
        """Context manager entry."""
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
        return False

    @property
    def is_open(self) -> bool:
        """Check if the recorder is currently open."""
        return self._is_open

    @property
    def file_path(self) -> str:
        """Get the full path to the recording file."""
        return str(self.filepath)
