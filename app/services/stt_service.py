"""Speech-to-Text service with support for Vosk and Whisper."""

import asyncio
import json
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

import numpy as np
import torch
from loguru import logger

from app.core.config import get_settings


class STTEngine(ABC):
    """Abstract base class for STT engines."""

    @abstractmethod
    async def transcribe(self, audio_data: bytes) -> tuple[str, Optional[float]]:
        """Transcribe audio to text.

        Returns:
            Tuple of (transcribed_text, confidence_score)
        """
        pass

    @abstractmethod
    async def transcribe_stream(self, audio_chunk: bytes) -> Optional[str]:
        """Transcribe streaming audio chunk.

        Returns:
            Partial or final transcription if available.
        """
        pass


class VoskSTTEngine(STTEngine):
    """Vosk-based STT engine for ultra-fast real-time transcription."""

    def __init__(self, model_path: str, sample_rate: int = 16000):
        """Initialize Vosk STT engine.

        Args:
            model_path: Path to Vosk model directory
            sample_rate: Audio sample rate in Hz
        """
        try:
            from vosk import Model, KaldiRecognizer

            self.sample_rate = sample_rate

            # Check if model exists
            model_dir = Path(model_path)
            if not model_dir.exists():
                raise FileNotFoundError(
                    f"Vosk model not found at {model_path}. "
                    f"Please download from https://alphacephei.com/vosk/models"
                )

            logger.info(f"Loading Vosk model from {model_path}")
            self.model = Model(str(model_dir))
            self.recognizer = KaldiRecognizer(self.model, sample_rate)
            self.recognizer.SetWords(True)
            logger.info("Vosk STT engine initialized successfully")

        except ImportError:
            raise ImportError("Vosk not installed. Install with: pip install vosk")

    async def transcribe(self, audio_data: bytes) -> tuple[str, Optional[float]]:
        """Transcribe complete audio to text."""
        # Run in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, self._transcribe_sync, audio_data)
        return result

    def _transcribe_sync(self, audio_data: bytes) -> tuple[str, Optional[float]]:
        """Synchronous transcription."""
        from vosk import KaldiRecognizer

        # Create new recognizer for this transcription
        recognizer = KaldiRecognizer(self.model, self.sample_rate)
        recognizer.SetWords(True)

        # Convert bytes to numpy array
        audio_np = np.frombuffer(audio_data, dtype=np.int16)

        # Process audio
        recognizer.AcceptWaveform(audio_np.tobytes())
        result = json.loads(recognizer.FinalResult())

        text = result.get("text", "")
        confidence = result.get("result", [{}])[0].get("conf", None) if result.get("result") else None

        return text, confidence

    async def transcribe_stream(self, audio_chunk: bytes) -> Optional[str]:
        """Transcribe streaming audio chunk."""
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, self._transcribe_stream_sync, audio_chunk)
        return result

    def _transcribe_stream_sync(self, audio_chunk: bytes) -> Optional[str]:
        """Synchronous streaming transcription."""
        if self.recognizer.AcceptWaveform(audio_chunk):
            result = json.loads(self.recognizer.Result())
            return result.get("text", "")
        else:
            # Partial result
            partial = json.loads(self.recognizer.PartialResult())
            return partial.get("partial", "")


class WhisperSTTEngine(STTEngine):
    """Whisper-based STT engine for high-accuracy transcription."""

    def __init__(self, model_name: str = "base", language: str = "ar", device: Optional[str] = None):
        """Initialize Whisper STT engine.

        Args:
            model_name: Whisper model size (tiny, base, small, medium, large)
            language: Language code for transcription
            device: Device to run model on (cuda/cpu)
        """
        try:
            import whisper

            if device is None:
                device = "cuda" if torch.cuda.is_available() else "cpu"

            logger.info(f"Loading Whisper model '{model_name}' on {device}")
            self.model = whisper.load_model(model_name, device=device)
            self.language = language
            self.device = device
            logger.info("Whisper STT engine initialized successfully")

        except ImportError:
            raise ImportError("Whisper not installed. Install with: pip install openai-whisper")

    async def transcribe(self, audio_data: bytes) -> tuple[str, Optional[float]]:
        """Transcribe complete audio to text."""
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, self._transcribe_sync, audio_data)
        return result

    def _transcribe_sync(self, audio_data: bytes) -> tuple[str, Optional[float]]:
        """Synchronous transcription."""
        # Convert bytes to float32 array normalized to [-1, 1]
        audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0

        # Transcribe
        result = self.model.transcribe(
            audio_np,
            language=self.language,
            fp16=False if self.device == "cpu" else True
        )

        text = result.get("text", "").strip()
        # Whisper doesn't provide word-level confidence, use segment confidence
        segments = result.get("segments", [])
        confidence = np.mean([s.get("no_speech_prob", 0) for s in segments]) if segments else None

        return text, confidence

    async def transcribe_stream(self, audio_chunk: bytes) -> Optional[str]:
        """Whisper doesn't support true streaming, buffer and transcribe."""
        # For streaming, consider using faster-whisper or whisper-streaming
        logger.warning("Whisper doesn't support true streaming. Use Vosk for real-time.")
        return None


class STTService:
    """Main STT service that manages different engines."""

    def __init__(self):
        """Initialize STT service with configured engine."""
        settings = get_settings()
        self.settings = settings

        if settings.stt_engine == "vosk":
            self.engine = VoskSTTEngine(
                model_path=settings.vosk_model_path,
                sample_rate=settings.sample_rate
            )
        elif settings.stt_engine == "whisper":
            self.engine = WhisperSTTEngine(
                model_name=settings.whisper_model,
                language=settings.whisper_language
            )
        else:
            raise ValueError(f"Unknown STT engine: {settings.stt_engine}")

        logger.info(f"STT Service initialized with {settings.stt_engine} engine")

    async def transcribe(self, audio_data: bytes) -> tuple[str, Optional[float], float]:
        """Transcribe audio to text.

        Returns:
            Tuple of (text, confidence, processing_time_ms)
        """
        start_time = time.perf_counter()
        text, confidence = await self.engine.transcribe(audio_data)
        processing_time = (time.perf_counter() - start_time) * 1000

        logger.debug(f"Transcribed in {processing_time:.2f}ms: {text[:50]}...")
        return text, confidence, processing_time

    async def transcribe_stream(self, audio_chunk: bytes) -> Optional[str]:
        """Transcribe streaming audio chunk."""
        return await self.engine.transcribe_stream(audio_chunk)
