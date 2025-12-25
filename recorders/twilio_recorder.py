"""
Twilio-specific audio recorder that converts mulaw to linear PCM.
"""

import asyncio

from recorders.conversation_recorder import ConversationRecorder
from utils.audio_utils import AudioUtils
from utils.logger import get_logger

logger = get_logger(__name__)


class TwilioConversationRecorder(ConversationRecorder):
    """
    Recorder for Twilio conversations.

    Converts mulaw-encoded audio (8kHz, 8-bit) to linear PCM (8kHz, 16-bit)
    before recording to WAV file.
    """

    def __init__(
        self,
        conversation_id: str,
        recording_path: str = "recordings",
    ):
        """
        Initialize the Twilio conversation recorder.

        Args:
            conversation_id: Unique identifier for the conversation
            recording_path: Directory to save recordings (default: "recordings/")
        """
        # Record as 16-bit linear PCM at 8kHz
        super().__init__(
            conversation_id=conversation_id,
            recording_path=recording_path,
            sample_rate=8000,  # Twilio standard
            channels=1,  # Mono
            sample_width=2,  # 16-bit PCM (converted from mulaw)
        )

    async def _flush_buffer(self) -> None:
        """
        Flush buffered audio chunks to file.

        Override to handle mulaw conversion for Twilio audio.
        """
        async with self._buffer_lock:
            if not self._audio_buffer:
                return

            # Extract all chunks and clear buffer
            chunks = list(self._audio_buffer)
            self._audio_buffer.clear()
            self._current_buffer_size = 0

        # Sort chunks by timestamp to maintain chronological order
        chunks.sort(key=lambda x: x[0])  # Sort by timestamp

        # Extract raw audio data (mulaw format from Twilio)
        raw_audio_chunks = [audio_data for _, audio_data in chunks]

        # Write all chunks using batch conversion pattern with mulaw conversion
        if raw_audio_chunks:
            try:
                # Close the file handle if it's open (AudioUtils will handle file operations)
                if self._wav_file is not None:
                    with self._lock:
                        if self._wav_file is not None:
                            self._wav_file.close()
                            self._wav_file = None

                # Use AudioUtils to batch convert mulaw to PCM and write
                await asyncio.to_thread(
                    AudioUtils.to_thread_flush_audio_frames,
                    raw_audio_chunks,
                    str(self.filepath),
                    self.sample_rate,
                    self.channels,
                    self.sample_width,
                    convert_mulaw=True,  # Twilio audio is in mulaw format
                )
            except Exception as e:
                logger.error(f"[{self.conversation_id}] Error writing buffered audio: {e}")
