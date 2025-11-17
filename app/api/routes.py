"""API routes for voice agent."""

import asyncio
import base64
import json
import time
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, UploadFile, File, HTTPException
from fastapi.responses import Response
from loguru import logger

from app.models.schemas import (
    TranscriptionResponse,
    TTSResponse,
    ChatRequest,
    ChatResponse,
    VisemeFrameSchema,
)
from app.services.stt_service import STTService
from app.services.tts_service import TTSService
from app.services.ai_agent import AIAgent
from app.services.knowledge_base import KnowledgeBase
from app.services.lipsync_service import LipSyncService

# Initialize services (will be set by main app)
stt_service: Optional[STTService] = None
tts_service: Optional[TTSService] = None
ai_agent: Optional[AIAgent] = None
knowledge_base: Optional[KnowledgeBase] = None
lipsync_service: Optional[LipSyncService] = None


def set_services(
    stt: STTService,
    tts: TTSService,
    agent: AIAgent,
    kb: KnowledgeBase,
    lipsync: Optional[LipSyncService] = None
) -> None:
    """Set service instances."""
    global stt_service, tts_service, ai_agent, knowledge_base, lipsync_service
    stt_service = stt
    tts_service = tts
    ai_agent = agent
    knowledge_base = kb
    lipsync_service = lipsync


router = APIRouter()


@router.get("/health")
async def health_check() -> dict:
    """Health check endpoint."""
    return {
        "status": "healthy",
        "services": {
            "stt": stt_service is not None,
            "tts": tts_service is not None,
            "ai_agent": ai_agent is not None,
            "knowledge_base": knowledge_base is not None,
        }
    }


@router.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe_audio(audio: UploadFile = File(...)) -> TranscriptionResponse:
    """Transcribe audio file to text.

    Args:
        audio: Audio file upload

    Returns:
        Transcription response with text and metadata
    """
    if not stt_service:
        raise HTTPException(status_code=503, detail="STT service not available")

    try:
        # Read audio data
        audio_data = await audio.read()

        # Transcribe
        text, confidence, processing_time = await stt_service.transcribe(audio_data)

        return TranscriptionResponse(
            text=text,
            confidence=confidence,
            language="ar",
            processing_time_ms=processing_time
        )

    except Exception as e:
        logger.error(f"Transcription error: {e}")
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")


@router.post("/synthesize")
async def synthesize_speech(text: str, voice: Optional[str] = None) -> Response:
    """Synthesize text to speech.

    Args:
        text: Text to synthesize
        voice: Optional voice to use

    Returns:
        Audio file response
    """
    if not tts_service:
        raise HTTPException(status_code=503, detail="TTS service not available")

    try:
        # Synthesize
        audio_data, processing_time = await tts_service.synthesize(text, voice=voice)

        logger.info(f"Synthesized speech in {processing_time:.2f}ms")

        return Response(
            content=audio_data,
            media_type="audio/mpeg",
            headers={
                "X-Processing-Time-Ms": str(processing_time)
            }
        )

    except Exception as e:
        logger.error(f"Synthesis error: {e}")
        raise HTTPException(status_code=500, detail=f"Synthesis failed: {str(e)}")


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """Chat with AI agent.

    Args:
        request: Chat request with message

    Returns:
        AI agent response
    """
    if not ai_agent:
        raise HTTPException(status_code=503, detail="AI agent not available")

    try:
        # Generate response
        response, sources, processing_time = await ai_agent.generate_response(
            message=request.message,
            use_knowledge_base=request.use_knowledge_base
        )

        return ChatResponse(
            response=response,
            sources=sources,
            processing_time_ms=processing_time
        )

    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")


@router.websocket("/ws/conversation")
async def websocket_conversation(websocket: WebSocket) -> None:
    """WebSocket endpoint for real-time voice conversation.

    Protocol:
        Client sends: {"type": "audio", "data": "<base64_audio>"}
        Server sends: {"type": "transcription", "data": {"text": "..."}}
        Server sends: {"type": "response", "data": {"text": "...", "audio": "<base64>"}}
    """
    await websocket.accept()
    logger.info("WebSocket connection established")

    if not all([stt_service, tts_service, ai_agent]):
        await websocket.send_json({
            "type": "error",
            "data": {"message": "Services not fully initialized"}
        })
        await websocket.close()
        return

    try:
        while True:
            # Receive message from client
            message = await websocket.receive_json()
            msg_type = message.get("type")

            if msg_type == "audio":
                # Process audio data
                audio_b64 = message.get("data")
                if not audio_b64:
                    continue

                # Decode audio
                audio_data = base64.b64decode(audio_b64)

                # Transcribe
                start_time = time.perf_counter()
                text, confidence, trans_time = await stt_service.transcribe(audio_data)

                if not text.strip():
                    await websocket.send_json({
                        "type": "info",
                        "data": {"message": "No speech detected"}
                    })
                    continue

                # Send transcription
                await websocket.send_json({
                    "type": "transcription",
                    "data": {
                        "text": text,
                        "confidence": confidence,
                        "processing_time_ms": trans_time
                    }
                })

                # Generate AI response
                response_text, sources, ai_time = await ai_agent.generate_response(
                    message=text,
                    use_knowledge_base=True
                )

                # Synthesize response
                audio_response, tts_time = await tts_service.synthesize(response_text)

                # Generate visemes if lip-sync service available
                visemes_data = []
                lipsync_time = 0.0
                if lipsync_service and lipsync_service.enabled:
                    try:
                        viseme_frames, lipsync_time = await lipsync_service.generate_visemes(
                            audio_data=audio_response,
                            text=response_text,
                            audio_format="mp3"
                        )
                        visemes_data = [v.to_dict() for v in viseme_frames]
                    except Exception as e:
                        logger.warning(f"Lip-sync generation failed: {e}")

                # Encode audio to base64
                audio_b64_response = base64.b64encode(audio_response).decode('utf-8')

                total_time = (time.perf_counter() - start_time) * 1000

                # Send response
                response_data = {
                    "text": response_text,
                    "audio": audio_b64_response,
                    "sources": sources,
                    "processing_times": {
                        "transcription_ms": trans_time,
                        "ai_generation_ms": ai_time,
                        "synthesis_ms": tts_time,
                        "lipsync_ms": lipsync_time,
                        "total_ms": total_time
                    }
                }

                # Include visemes if available
                if visemes_data:
                    response_data["visemes"] = visemes_data

                await websocket.send_json({
                    "type": "response",
                    "data": response_data
                })

                logger.info(f"Full conversation cycle: {total_time:.2f}ms")

            elif msg_type == "text":
                # Direct text input (skip STT)
                text = message.get("data")
                if not text:
                    continue

                # Generate AI response
                response_text, sources, ai_time = await ai_agent.generate_response(
                    message=text,
                    use_knowledge_base=True
                )

                # Synthesize response
                audio_response, tts_time = await tts_service.synthesize(response_text)

                # Generate visemes if lip-sync service available
                visemes_data = []
                lipsync_time = 0.0
                if lipsync_service and lipsync_service.enabled:
                    try:
                        viseme_frames, lipsync_time = await lipsync_service.generate_visemes(
                            audio_data=audio_response,
                            text=response_text,
                            audio_format="mp3"
                        )
                        visemes_data = [v.to_dict() for v in viseme_frames]
                    except Exception as e:
                        logger.warning(f"Lip-sync generation failed: {e}")

                audio_b64_response = base64.b64encode(audio_response).decode('utf-8')

                # Send response
                response_data = {
                    "text": response_text,
                    "audio": audio_b64_response,
                    "sources": sources,
                    "processing_times": {
                        "ai_generation_ms": ai_time,
                        "synthesis_ms": tts_time,
                        "lipsync_ms": lipsync_time,
                        "total_ms": ai_time + tts_time + lipsync_time
                    }
                }

                # Include visemes if available
                if visemes_data:
                    response_data["visemes"] = visemes_data

                await websocket.send_json({
                    "type": "response",
                    "data": response_data
                })

            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        logger.info("WebSocket connection closed")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "data": {"message": str(e)}
            })
        except:
            pass
    finally:
        try:
            await websocket.close()
        except:
            pass
