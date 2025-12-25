"""
Audio utility functions for thread-safe file operations.
"""

import audioop
import wave
from pathlib import Path


class AudioUtils:
    """Utility class for audio file operations."""

    @staticmethod
    def to_thread_flush_audio_frames(
        audio_buffer: list[bytes],
        filename: str,
        sample_rate: int = 8000,
        channels: int = 1,
        sample_width: int = 2,
        convert_mulaw: bool = False,
    ) -> None:
        """
        Flush audio frames to a WAV file in a thread-safe manner.

        This method combines all audio chunks, optionally converts them,
        and writes to file in one atomic operation. Designed to be called
        via asyncio.to_thread to prevent blocking the event loop.

        Based on the pattern: combine all chunks -> convert all at once -> write all at once

        Args:
            audio_buffer: List of audio frame bytes to write
            filename: Path to the WAV file
            sample_rate: Audio sample rate in Hz (default: 8000)
            channels: Number of audio channels (default: 1 for mono)
            sample_width: Sample width in bytes (default: 2 for 16-bit)
            convert_mulaw: If True, convert mulaw to linear PCM (default: False)
        """
        if not audio_buffer:
            return

        filepath = Path(filename)

        try:
            # Combine all audio chunks (like the sample: b''.join(audio_buffer))
            combined_audio = b"".join(audio_buffer)

            # Convert if needed (like the sample: audioop.ulaw2lin(mulaw_audio, 2))
            if convert_mulaw:
                # Convert mulaw (8-bit) to linear PCM (16-bit)
                combined_audio = audioop.ulaw2lin(combined_audio, sample_width)

            # Check if file exists - if so, we need to append to it
            if filepath.exists():
                # Read existing audio data
                with wave.open(str(filepath), "rb") as rf:
                    params = rf.getparams()
                    existing_audio = rf.readframes(rf.getnframes())

                # Combine existing and new audio
                all_audio = existing_audio + combined_audio

                # Write everything back with same parameters
                with wave.open(str(filepath), "wb") as wf:
                    wf.setnchannels(params.nchannels)
                    wf.setsampwidth(params.sampwidth)
                    wf.setframerate(params.framerate)
                    wf.writeframes(all_audio)
            else:
                # Write new file
                with wave.open(str(filepath), "wb") as wav_file:
                    wav_file.setnchannels(channels)
                    wav_file.setsampwidth(sample_width)
                    wav_file.setframerate(sample_rate)
                    wav_file.writeframes(combined_audio)

        except Exception as e:
            raise RuntimeError(f"Error flushing audio frames to {filename}: {e}")
