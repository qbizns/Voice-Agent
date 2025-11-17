"""Pydantic schemas for request/response models."""

from typing import Optional
from pydantic import BaseModel, Field


class TranscriptionRequest(BaseModel):
    """Request model for audio transcription."""
    audio_data: bytes
    language: str = Field(default="ar", description="Language code for transcription")


class TranscriptionResponse(BaseModel):
    """Response model for audio transcription."""
    text: str
    confidence: Optional[float] = None
    language: str = "ar"
    processing_time_ms: float


class TTSRequest(BaseModel):
    """Request model for text-to-speech."""
    text: str
    voice: Optional[str] = None
    rate: Optional[str] = None
    volume: Optional[str] = None


class TTSResponse(BaseModel):
    """Response model for text-to-speech."""
    audio_data: bytes
    format: str = "mp3"
    processing_time_ms: float


class ChatRequest(BaseModel):
    """Request model for chat interaction."""
    message: str
    use_knowledge_base: bool = True


class ChatResponse(BaseModel):
    """Response model for chat interaction."""
    response: str
    sources: Optional[list[str]] = None
    processing_time_ms: float


class ConversationMessage(BaseModel):
    """WebSocket message for real-time conversation."""
    type: str  # "audio", "text", "response", "error", "info"
    data: str | bytes | dict
    timestamp: Optional[float] = None
