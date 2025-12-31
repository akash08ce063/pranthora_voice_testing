#!/usr/bin/env python3

import asyncio
import json
import uuid
import base64
import websockets
import logging
import sys
import time
import audioop
import wave

# ---------------- LOGGING ----------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger("TwilioSim")

# ---------------- CONFIGURATION ----------------

AGENT_ID_A = "d7794b6e-20ff-4e28-9a97-98e327eea2d3"
AGENT_ID_B = "028cdb34-ef3e-40d9-a4bd-35b92d9c5d29"

WS_URL_BASE = "ws://localhost:5050"

# Audio settings
CHUNK_SIZE = 160          # 20ms @ 8kHz
SAMPLE_RATE = 8000
SILENCE_BYTE = b"\xff"    # μ-law silence

RECORD_WAV_FILE = "bridge_recording.wav"
MAX_DURATION_SEC = 30

# ---------------- GLOBAL RECORDER ----------------

pcm_frames = bytearray()
stop_event = asyncio.Event()

def record_ulaw_to_pcm(ulaw_audio: bytes):
    """
    Convert μ-law → PCM16 and store.
    Recording ONLY happens here (read side).
    """
    pcm = audioop.ulaw2lin(ulaw_audio, 2)  # 16-bit PCM
    pcm_frames.extend(pcm)


# ---------------- AGENT CONNECTION ----------------

async def agent_connection(
    name: str,
    agent_id: str,
    call_sid: str,
    incoming_queue: asyncio.Queue,
    outgoing_queue: asyncio.Queue,
):
    """
    Manages a single agent WebSocket connection.
    Reads audio from agent -> outgoing_queue
    Writes audio from incoming_queue -> agent (20ms cadence)
    """

    ws_url = f"{WS_URL_BASE}/api/call/media-stream/agents/{agent_id}?call_sid={call_sid}"
    logger.info(f"[{name}] Connecting to {ws_url}")

    try:
        async with websockets.connect(ws_url) as websocket:

            # -------- START EVENT --------

            start_event = {
                "event": "start",
                "sequenceNumber": "1",
                "start": {
                    "accountSid": "AC_SIMULATION",
                    "callSid": call_sid,
                    "streamSid": f"stream_{call_sid}",
                    "tracks": ["inbound"],
                    "customParameters": {},
                },
                "streamSid": f"stream_{call_sid}",
            }

            await websocket.send(json.dumps(start_event))
            logger.info(f"[{name}] Sent start event")

            # -------- READ FROM AGENT --------

            async def read_from_ws():
                try:
                    async for message in websocket:
                        if stop_event.is_set():
                            break

                        data = json.loads(message)
                        event_type = data.get("event")

                        if event_type == "media":
                            payload = data["media"]["payload"]
                            ulaw_audio = base64.b64decode(payload)

                            # ✅ RECORD ONLY ON READ (NO DUPLICATION)
                            record_ulaw_to_pcm(ulaw_audio)

                            await outgoing_queue.put(ulaw_audio)

                        elif event_type == "mark":
                            logger.info(
                                f"[{name}] Mark: {data.get('mark', {}).get('name')}"
                            )

                        elif event_type == "clear":
                            logger.info(f"[{name}] Clear received")
                            while not incoming_queue.empty():
                                try:
                                    incoming_queue.get_nowait()
                                except asyncio.QueueEmpty:
                                    break

                        elif event_type == "stop":
                            logger.info(f"[{name}] Stop received")
                            break

                except Exception as e:
                    logger.error(f"[{name}] Read error: {e}")

            # -------- WRITE TO AGENT (20ms) --------

            async def write_to_ws():
                stream_sid = f"stream_{call_sid}"
                next_tick = time.time()

                try:
                    while not stop_event.is_set():
                        next_tick += 0.02
                        sleep_time = next_tick - time.time()
                        if sleep_time > 0:
                            await asyncio.sleep(sleep_time)

                        payload_b64 = None

                        if not incoming_queue.empty():
                            try:
                                audio = incoming_queue.get_nowait()
                                payload_b64 = base64.b64encode(audio).decode()
                            except asyncio.QueueEmpty:
                                pass

                        if not payload_b64:
                            silence = SILENCE_BYTE * CHUNK_SIZE
                            payload_b64 = base64.b64encode(silence).decode()

                        media_event = {
                            "event": "media",
                            "streamSid": stream_sid,
                            "media": {"payload": payload_b64},
                        }

                        await websocket.send(json.dumps(media_event))

                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    logger.error(f"[{name}] Write error: {e}")

            reader_task = asyncio.create_task(read_from_ws())
            writer_task = asyncio.create_task(write_to_ws())

            await reader_task
            writer_task.cancel()

    except Exception as e:
        logger.error(f"[{name}] Connection failed: {e}")


# ---------------- MAIN ----------------

async def main():
    queue_a_to_b = asyncio.Queue()
    queue_b_to_a = asyncio.Queue()

    call_sid_a = str(uuid.uuid4())
    call_sid_b = str(uuid.uuid4())

    logger.info("Starting agent bridge")
    logger.info(f"Agent A: {AGENT_ID_A}")
    logger.info(f"Agent B: {AGENT_ID_B}")

    task_a = asyncio.create_task(
        agent_connection(
            "Agent A",
            AGENT_ID_A,
            call_sid_a,
            incoming_queue=queue_b_to_a,
            outgoing_queue=queue_a_to_b,
        )
    )

    task_b = asyncio.create_task(
        agent_connection(
            "Agent B",
            AGENT_ID_B,
            call_sid_b,
            incoming_queue=queue_a_to_b,
            outgoing_queue=queue_b_to_a,
        )
    )

    # -------- HARD STOP AFTER TIMEOUT --------
    await asyncio.sleep(MAX_DURATION_SEC)
    logger.info("⏹️ 15 seconds reached, shutting down bridge")

    stop_event.set()

    task_a.cancel()
    task_b.cancel()

    await asyncio.gather(task_a, task_b, return_exceptions=True)

    # -------- WRITE WAV FILE --------
    with wave.open(RECORD_WAV_FILE, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)     # 16-bit PCM
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm_frames)

    logger.info(f"🎙️ Bridge audio saved: {RECORD_WAV_FILE}")
    logger.info(f"PCM bytes written: {len(pcm_frames)}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Simulation stopped by user")
