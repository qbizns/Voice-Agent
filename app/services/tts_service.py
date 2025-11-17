"""Text-to-Speech service with support for Edge TTS and Coqui TTS."""

import asyncio
import io
import time
from abc import ABC, abstractmethod
from typing import Optional

from loguru import logger

from app.core.config import get_settings


class TTSEngine(ABC):
    """Abstract base class for TTS engines."""

    @abstractmethod
    async def synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
        rate: Optional[str] = None,
        volume: Optional[str] = None
    ) -> bytes:
        """Synthesize text to speech audio.

        Returns:
            Audio data in bytes
        """
        pass


class EdgeTTSEngine(TTSEngine):
    """Edge TTS engine for high-quality, fast Arabic speech synthesis."""

    def __init__(self, default_voice: str, default_rate: str, default_volume: str):
        """Initialize Edge TTS engine.

        Args:
            default_voice: Default voice to use (e.g., ar-EG-SalmaNeural)
            default_rate: Default speech rate (e.g., +0%)
            default_volume: Default volume (e.g., +0%)
        """
        try:
            import edge_tts

            self.edge_tts = edge_tts
            self.default_voice = default_voice
            self.default_rate = default_rate
            self.default_volume = default_volume
            logger.info(f"Edge TTS engine initialized with voice: {default_voice}")

        except ImportError:
            raise ImportError("Edge TTS not installed. Install with: pip install edge-tts")

    async def synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
        rate: Optional[str] = None,
        volume: Optional[str] = None
    ) -> bytes:
        """Synthesize text to speech using Edge TTS."""
        voice = voice or self.default_voice
        rate = rate or self.default_rate
        volume = volume or self.default_volume

        # Create communicate instance
        communicate = self.edge_tts.Communicate(
            text=text,
            voice=voice,
            rate=rate,
            volume=volume
        )

        # Collect audio chunks
        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]

        return audio_data


class CoquiTTSEngine(TTSEngine):
    """Coqui TTS engine for offline, high-quality speech synthesis."""

    def __init__(self, model_name: str = "tts_models/ar/cv/vits"):
        """Initialize Coqui TTS engine.

        Args:
            model_name: Coqui TTS model name
        """
        try:
            from TTS.api import TTS
            import torch

            device = "cuda" if torch.cuda.is_available() else "cpu"

            logger.info(f"Loading Coqui TTS model '{model_name}' on {device}")
            self.tts = TTS(model_name=model_name).to(device)
            self.device = device
            logger.info("Coqui TTS engine initialized successfully")

        except ImportError:
            raise ImportError("Coqui TTS not installed. Install with: pip install TTS")

    async def synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
        rate: Optional[str] = None,
        volume: Optional[str] = None
    ) -> bytes:
        """Synthesize text to speech using Coqui TTS."""
        loop = asyncio.get_event_loop()
        audio_data = await loop.run_in_executor(None, self._synthesize_sync, text)
        return audio_data

    def _synthesize_sync(self, text: str) -> bytes:
        """Synchronous synthesis."""
        import numpy as np
        import soundfile as sf

        # Synthesize to numpy array
        wav = self.tts.tts(text=text)

        # Convert to bytes (16-bit PCM)
        wav_array = np.array(wav)
        wav_int16 = (wav_array * 32767).astype(np.int16)

        # Write to bytes buffer
        buffer = io.BytesIO()
        sf.write(buffer, wav_int16, self.tts.synthesizer.output_sample_rate, format='WAV')
        buffer.seek(0)

        return buffer.read()


class TTSService:
    """Main TTS service that manages different engines."""

    def __init__(self):
        """Initialize TTS service with configured engine."""
        settings = get_settings()
        self.settings = settings

        if settings.tts_engine == "edge":
            self.engine = EdgeTTSEngine(
                default_voice=settings.tts_voice,
                default_rate=settings.tts_rate,
                default_volume=settings.tts_volume
            )
        elif settings.tts_engine == "coqui":
            self.engine = CoquiTTSEngine()
        else:
            raise ValueError(f"Unknown TTS engine: {settings.tts_engine}")

        logger.info(f"TTS Service initialized with {settings.tts_engine} engine")

    async def synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
        rate: Optional[str] = None,
        volume: Optional[str] = None
    ) -> tuple[bytes, float]:
        """Synthesize text to speech.

        Returns:
            Tuple of (audio_data, processing_time_ms)
        """
        start_time = time.perf_counter()
        audio_data = await self.engine.synthesize(text, voice, rate, volume)
        processing_time = (time.perf_counter() - start_time) * 1000

        logger.debug(f"Synthesized speech in {processing_time:.2f}ms for text: {text[:50]}...")
        return audio_data, processing_time
