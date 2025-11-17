"""Live streaming routes for real-time voice interaction."""

import asyncio
import base64
import json
import time
import numpy as np
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from loguru import logger

from app.services.stt_service import STTService
from app.services.tts_service import TTSService
from app.services.ai_agent import AIAgent
from app.services.knowledge_base import KnowledgeBase
from app.services.vad_service import VADService, StreamingVAD
from app.services.context_service import ContextService
from app.services.cache_service import ResponseCache

# Initialize services (will be set by main app)
stt_service: Optional[STTService] = None
tts_service: Optional[TTSService] = None
ai_agent: Optional[AIAgent] = None
knowledge_base: Optional[KnowledgeBase] = None
vad_service: Optional[VADService] = None
context_service: Optional[ContextService] = None
cache_service: Optional[ResponseCache] = None


def set_services(
    stt: STTService,
    tts: TTSService,
    agent: AIAgent,
    kb: KnowledgeBase,
    vad: Optional[VADService] = None,
    context: Optional[ContextService] = None,
    cache: Optional[ResponseCache] = None
) -> None:
    """Set service instances."""
    global stt_service, tts_service, ai_agent, knowledge_base, vad_service, context_service, cache_service
    stt_service = stt
    tts_service = tts
    ai_agent = agent
    knowledge_base = kb
    vad_service = vad
    context_service = context
    cache_service = cache


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

    def __init__(
        self,
        session_id: str,
        sample_rate: int = 16000,
        channels: int = 1,
        use_vad: bool = True,
        vad_service: Optional[VADService] = None
    ):
        """Initialize session.

        Args:
            session_id: Unique session identifier
            sample_rate: Audio sample rate in Hz
            channels: Number of audio channels
            use_vad: Enable voice activity detection
            vad_service: VAD service instance
        """
        self.session_id = session_id
        self.sample_rate = sample_rate
        self.channels = channels
        self.audio_buffer = bytearray()
        self.is_active = True
        self.start_time = time.time()

        # Interruption state
        self.is_ai_responding = False
        self.interruption_requested = False
        self.cancel_event = asyncio.Event()

        # VAD setup
        self.use_vad = use_vad and vad_service is not None and vad_service.enabled
        self.streaming_vad = None
        if self.use_vad:
            self.streaming_vad = StreamingVAD(vad_service, silence_duration_ms=800)
            logger.info(f"VAD enabled for session {session_id}")
        else:
            logger.info(f"VAD disabled for session {session_id}")

        logger.info(f"Live session started: {session_id} ({sample_rate}Hz, {channels}ch)")

    def add_audio_chunk(self, pcm16_bytes: bytes) -> dict:
        """Add audio chunk to buffer and process VAD.

        Args:
            pcm16_bytes: PCM16 audio data

        Returns:
            VAD state dict with is_speaking, speech_ended, confidence, etc.
        """
        self.audio_buffer.extend(pcm16_bytes)
        logger.debug(f"Session {self.session_id}: buffer size = {len(self.audio_buffer)} bytes")

        # Process VAD if enabled
        if self.use_vad and self.streaming_vad:
            # Convert PCM16 bytes to float32 numpy array
            audio_np = np.frombuffer(pcm16_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            vad_state = self.streaming_vad.process_audio(audio_np)
            return vad_state

        return {
            "is_speaking": False,
            "speech_ended": False,
            "confidence": 0.0,
            "silence_duration_ms": 0.0,
        }

    def get_audio_data(self) -> bytes:
        """Get buffered audio data.

        Returns:
            Complete audio data as bytes
        """
        return bytes(self.audio_buffer)

    def clear_buffer(self) -> None:
        """Clear audio buffer."""
        self.audio_buffer.clear()
        if self.streaming_vad:
            self.streaming_vad.reset()

    def request_interruption(self) -> None:
        """Request interruption of current AI response."""
        if self.is_ai_responding:
            logger.info(f"Session {self.session_id}: Interruption requested")
            self.interruption_requested = True
            self.cancel_event.set()

    def start_response(self) -> None:
        """Mark that AI is starting to respond."""
        self.is_ai_responding = True
        self.interruption_requested = False
        self.cancel_event.clear()
        logger.debug(f"Session {self.session_id}: AI response started")

    def end_response(self) -> None:
        """Mark that AI response has ended."""
        self.is_ai_responding = False
        self.interruption_requested = False
        self.cancel_event.clear()
        logger.debug(f"Session {self.session_id}: AI response ended")

    def is_cancelled(self) -> bool:
        """Check if current operation should be cancelled."""
        return self.cancel_event.is_set()

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
                    use_vad = data.get("use_vad", True)

                    session = LiveSession(
                        session_id,
                        sample_rate,
                        channels,
                        use_vad=use_vad,
                        vad_service=vad_service
                    )

                    await websocket.send_json({
                        "type": "session_started",
                        "data": {
                            "session_id": session_id,
                            "vad_enabled": session.use_vad
                        }
                    })

                    logger.info(f"Session {session_id} started (VAD: {session.use_vad})")

                elif msg_type == "interrupt":
                    # Interrupt current AI response
                    if not session or not session.is_active:
                        logger.warning("Received interrupt without active session")
                        continue

                    session.request_interruption()
                    await websocket.send_json({
                        "type": "interrupted",
                        "data": {"session_id": session.session_id}
                    })
                    logger.info(f"Session {session.session_id}: Interrupted")

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
                        vad_state = session.add_audio_chunk(pcm16_bytes)
                        logger.debug(f"Received audio chunk: {len(pcm16_bytes)} bytes")

                        # Send VAD status update
                        if session.use_vad:
                            await websocket.send_json({
                                "type": "vad_status",
                                "data": {
                                    "is_speaking": vad_state["is_speaking"],
                                    "confidence": vad_state["confidence"],
                                    "silence_duration_ms": vad_state["silence_duration_ms"]
                                }
                            })

                            # Auto-interrupt if user speaks while AI is responding
                            if vad_state["is_speaking"] and session.is_ai_responding:
                                logger.info("VAD detected user speech during AI response - auto-interrupting")
                                session.request_interruption()
                                await websocket.send_json({
                                    "type": "interrupted",
                                    "data": {
                                        "session_id": session.session_id,
                                        "reason": "user_speech_detected"
                                    }
                                })

                            # Auto-trigger processing when speech ends
                            if vad_state["speech_ended"] and not session.is_ai_responding:
                                logger.info("VAD detected end of speech - auto-processing")

                                # Process the complete audio (same as "end" message)
                                audio_data = session.get_audio_data()

                                if len(audio_data) == 0:
                                    logger.warning("No audio data to process")
                                    continue

                                logger.info(f"Auto-processing {len(audio_data)} bytes of audio")

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

                                # Mark that AI is starting to respond
                                session.start_response()

                                try:
                                    # Check cache first
                                    cached_response = None
                                    if cache_service:
                                        cached_response = cache_service.get(text, use_semantic=True)

                                    if cached_response:
                                        # Cache hit - use cached response
                                        response_text, audio_response, sources = cached_response
                                        logger.info("Using cached response")
                                        ai_time = 0.0
                                        tts_time = 0.0

                                        # Encode audio to base64
                                        audio_b64 = base64.b64encode(audio_response).decode('utf-8')
                                    else:
                                        # Cache miss - generate new response
                                        # 2. AI Agent with conversation context
                                        logger.info("Running AI agent...")

                                        # Get conversation history if context service available
                                        conversation_history = None
                                        if context_service and session:
                                            ctx = context_service.get_or_create_context(session.session_id)
                                            conversation_history = [
                                                {"role": msg.role, "content": msg.content}
                                                for msg in ctx.get_messages()
                                            ]
                                            logger.debug(f"Using {len(conversation_history)} messages from history")

                                        response_text, sources, ai_time = await ai_agent.generate_response(
                                            message=text,
                                            use_knowledge_base=True,
                                            conversation_history=conversation_history
                                        )

                                        # Check if interrupted during AI generation
                                        if session.is_cancelled():
                                            logger.info("Response generation interrupted")
                                            session.clear_buffer()
                                            continue

                                        logger.info(f"AI response: {response_text[:100]}...")

                                        # 3. Text-to-Speech
                                        logger.info("Running TTS...")
                                        audio_response, tts_time = await tts_service.synthesize(response_text)

                                        # Check if interrupted during TTS
                                        if session.is_cancelled():
                                            logger.info("TTS generation interrupted")
                                            session.clear_buffer()
                                            continue

                                    # Cache the response for future requests
                                    if cache_service:
                                        cache_service.put(
                                            query=text,
                                            response_text=response_text,
                                            audio_data=audio_response,
                                            audio_format="mp3",
                                            sources=sources,
                                            ttl_seconds=3600  # 1 hour
                                        )

                                    # Encode audio to base64
                                    audio_b64 = base64.b64encode(audio_response).decode('utf-8')

                                # Save exchange to context
                                if context_service and session:
                                    ctx = context_service.get_or_create_context(session.session_id)
                                    ctx.add_exchange(
                                        user_msg=text,
                                        assistant_msg=response_text,
                                        user_metadata={"confidence": confidence},
                                        assistant_metadata={"sources": sources}
                                    )

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

                                finally:
                                    # Always mark response as ended
                                    session.end_response()

                    except Exception as e:
                        logger.error(f"Failed to process audio chunk: {e}")

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

                    # Mark that AI is starting to respond
                    session.start_response()

                    try:
                        # Check cache first
                        cached_response = None
                        if cache_service:
                            cached_response = cache_service.get(text, use_semantic=True)

                        if cached_response:
                            # Cache hit - use cached response
                            response_text, audio_response, sources = cached_response
                            logger.info("Using cached response")
                            ai_time = 0.0
                            tts_time = 0.0

                            # Encode audio to base64
                            audio_b64 = base64.b64encode(audio_response).decode('utf-8')
                        else:
                            # Cache miss - generate new response
                            # 2. AI Agent with conversation context
                            logger.info("Running AI agent...")

                            # Get conversation history if context service available
                            conversation_history = None
                            if context_service and session:
                                ctx = context_service.get_or_create_context(session.session_id)
                                conversation_history = [
                                    {"role": msg.role, "content": msg.content}
                                    for msg in ctx.get_messages()
                                ]
                                logger.debug(f"Using {len(conversation_history)} messages from history")

                            response_text, sources, ai_time = await ai_agent.generate_response(
                            message=text,
                            use_knowledge_base=True,
                            conversation_history=conversation_history
                        )

                            logger.info(f"AI response: {response_text[:100]}...")

                            # Check if interrupted during AI generation
                            if session.is_cancelled():
                                logger.info("Response generation interrupted")
                                session.clear_buffer()
                                continue

                            # 3. Text-to-Speech
                            logger.info("Running TTS...")
                            audio_response, tts_time = await tts_service.synthesize(response_text)

                            # Check if interrupted during TTS
                            if session.is_cancelled():
                                logger.info("TTS generation interrupted")
                                session.clear_buffer()
                                continue

                            # Cache the response for future requests
                            if cache_service:
                                cache_service.put(
                                    query=text,
                                    response_text=response_text,
                                    audio_data=audio_response,
                                    audio_format="mp3",
                                    sources=sources,
                                    ttl_seconds=3600  # 1 hour
                                )

                            # Encode audio to base64
                            audio_b64 = base64.b64encode(audio_response).decode('utf-8')

                        # Save exchange to context
                        if context_service and session:
                            ctx = context_service.get_or_create_context(session.session_id)
                            ctx.add_exchange(
                                user_msg=text,
                                assistant_msg=response_text,
                                user_metadata={"confidence": confidence},
                                assistant_metadata={"sources": sources}
                            )

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

                    finally:
                        # Always mark response as ended
                        session.end_response()

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
