"""Live streaming routes for real-time voice interaction."""

import asyncio
import base64
import json
import time
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from loguru import logger

from app.services.stt_service import STTService
from app.services.tts_service import TTSService
from app.services.ai_agent import AIAgent
from app.services.knowledge_base import KnowledgeBase

# Initialize services (will be set by main app)
stt_service: Optional[STTService] = None
tts_service: Optional[TTSService] = None
ai_agent: Optional[AIAgent] = None
knowledge_base: Optional[KnowledgeBase] = None


def set_services(stt: STTService, tts: TTSService, agent: AIAgent, kb: KnowledgeBase) -> None:
    """Set service instances."""
    global stt_service, tts_service, ai_agent, knowledge_base
    stt_service = stt
    tts_service = tts
    ai_agent = agent
    knowledge_base = kb


router = APIRouter()


@router.get("/live", response_class=HTMLResponse)
async def serve_live_page():
    """Serve the live demo HTML page."""
    html_path = Path("static/live.html")

    if not html_path.exists():
        return HTMLResponse(
            content="<h1>Error: live.html not found</h1><p>Please ensure static/live.html exists.</p>",
            status_code=404
        )

    with open(html_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    return HTMLResponse(content=html_content)


class LiveSession:
    """Manages a live audio streaming session."""

    def __init__(self, session_id: str, sample_rate: int = 16000, channels: int = 1):
        """Initialize session.

        Args:
            session_id: Unique session identifier
            sample_rate: Audio sample rate in Hz
            channels: Number of audio channels
        """
        self.session_id = session_id
        self.sample_rate = sample_rate
        self.channels = channels
        self.audio_buffer = bytearray()
        self.is_active = True
        self.start_time = time.time()

        logger.info(f"Live session started: {session_id} ({sample_rate}Hz, {channels}ch)")

    def add_audio_chunk(self, pcm16_bytes: bytes) -> None:
        """Add audio chunk to buffer.

        Args:
            pcm16_bytes: PCM16 audio data
        """
        self.audio_buffer.extend(pcm16_bytes)
        logger.debug(f"Session {self.session_id}: buffer size = {len(self.audio_buffer)} bytes")

    def get_audio_data(self) -> bytes:
        """Get buffered audio data.

        Returns:
            Complete audio data as bytes
        """
        return bytes(self.audio_buffer)

    def clear_buffer(self) -> None:
        """Clear audio buffer."""
        self.audio_buffer.clear()

    def close(self) -> None:
        """Close session."""
        self.is_active = False
        duration = time.time() - self.start_time
        logger.info(f"Live session ended: {self.session_id} (duration: {duration:.2f}s)")


@router.websocket("/live")
async def websocket_live_stream(websocket: WebSocket) -> None:
    """WebSocket endpoint for live audio streaming.

    Protocol:
        Client → Server:
            {"type": "start", "data": {"language": "ar", "session_id": "...", ...}}
            {"type": "audio_chunk", "data": {"sample_rate": 16000, "channels": 1, "pcm16": "<base64>"}}
            {"type": "end"}

        Server → Client:
            {"type": "session_started", "data": {"session_id": "..."}}
            {"type": "transcription", "data": {"text": "...", "is_final": true/false}}
            {"type": "response", "data": {"text": "...", "audio": "<base64>", "processing_times": {...}}}
            {"type": "error", "data": {"message": "..."}}
    """
    await websocket.accept()
    logger.info("Live WebSocket connection established")

    if not all([stt_service, tts_service, ai_agent]):
        await websocket.send_json({
            "type": "error",
            "data": {"message": "Services not fully initialized"}
        })
        await websocket.close()
        return

    session: Optional[LiveSession] = None

    try:
        while True:
            # Receive message from client
            raw_data = await websocket.receive_text()

            try:
                message = json.loads(raw_data)
                msg_type = message.get("type")

                if msg_type == "start":
                    # Start session
                    data = message.get("data", {})
                    session_id = data.get("session_id", f"live_{int(time.time())}")
                    sample_rate = data.get("sample_rate", 16000)
                    channels = data.get("channels", 1)

                    session = LiveSession(session_id, sample_rate, channels)

                    await websocket.send_json({
                        "type": "session_started",
                        "data": {"session_id": session_id}
                    })

                    logger.info(f"Session {session_id} started")

                elif msg_type == "audio_chunk":
                    # Receive audio chunk
                    if not session or not session.is_active:
                        logger.warning("Received audio chunk without active session")
                        continue

                    data = message.get("data", {})
                    pcm16_base64 = data.get("pcm16")

                    if not pcm16_base64:
                        logger.warning("Received empty audio chunk")
                        continue

                    # Decode base64 PCM16
                    try:
                        pcm16_bytes = base64.b64decode(pcm16_base64)
                        session.add_audio_chunk(pcm16_bytes)
                        logger.debug(f"Received audio chunk: {len(pcm16_bytes)} bytes")
                    except Exception as e:
                        logger.error(f"Failed to decode audio chunk: {e}")

                elif msg_type == "end":
                    # End of utterance - process complete audio
                    if not session or not session.is_active:
                        logger.warning("Received end signal without active session")
                        continue

                    logger.info(f"Processing session {session.session_id}")

                    # Get complete audio
                    audio_data = session.get_audio_data()

                    if len(audio_data) == 0:
                        logger.warning("No audio data to process")
                        await websocket.send_json({
                            "type": "error",
                            "data": {"message": "No audio data received"}
                        })
                        continue

                    logger.info(f"Processing {len(audio_data)} bytes of audio")

                    # Process the complete pipeline
                    start_time = time.perf_counter()

                    # 1. Speech-to-Text
                    logger.info("Running STT...")
                    text, confidence, stt_time = await stt_service.transcribe(audio_data)

                    if not text.strip():
                        logger.warning("No speech detected in audio")
                        await websocket.send_json({
                            "type": "transcription",
                            "data": {"text": "", "is_final": True}
                        })
                        session.clear_buffer()
                        continue

                    # Send transcription
                    await websocket.send_json({
                        "type": "transcription",
                        "data": {
                            "text": text,
                            "is_final": True,
                            "confidence": confidence
                        }
                    })

                    logger.info(f"Transcription: {text}")

                    # 2. AI Agent
                    logger.info("Running AI agent...")
                    response_text, sources, ai_time = await ai_agent.generate_response(
                        message=text,
                        use_knowledge_base=True
                    )

                    logger.info(f"AI response: {response_text[:100]}...")

                    # 3. Text-to-Speech
                    logger.info("Running TTS...")
                    audio_response, tts_time = await tts_service.synthesize(response_text)

                    # Encode audio to base64
                    audio_b64 = base64.b64encode(audio_response).decode('utf-8')

                    total_time = (time.perf_counter() - start_time) * 1000

                    # Send response
                    await websocket.send_json({
                        "type": "response",
                        "data": {
                            "text": response_text,
                            "audio": audio_b64,
                            "sources": sources,
                            "processing_times": {
                                "transcription_ms": stt_time,
                                "ai_generation_ms": ai_time,
                                "synthesis_ms": tts_time,
                                "total_ms": total_time
                            }
                        }
                    })

                    logger.info(f"Response sent (total: {total_time:.2f}ms)")

                    # Clear buffer for next utterance
                    session.clear_buffer()

                else:
                    logger.warning(f"Unknown message type: {msg_type}")

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse message: {e}")
                await websocket.send_json({
                    "type": "error",
                    "data": {"message": "Invalid JSON"}
                })

    except WebSocketDisconnect:
        logger.info("Live WebSocket connection closed by client")

    except Exception as e:
        logger.error(f"Live WebSocket error: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "data": {"message": str(e)}
            })
        except:
            pass

    finally:
        if session:
            session.close()

        try:
            await websocket.close()
        except:
            pass

        logger.info("Live WebSocket connection closed")
