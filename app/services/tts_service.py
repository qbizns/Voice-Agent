"""Text-to-Speech service with multi-dialect Arabic support.

Refactored to use:
- HybridTTSService (Edge/Google/ElevenLabs)
- Voice profiles with 32 Arabic voices
- SSML generation with Egyptian lexicon
- Phrase caching for performance
"""

import asyncio
import io
import time
from abc import ABC, abstractmethod
from typing import Optional

from loguru import logger

from app.core.config import get_settings
from .voice_profiles import get_voice_profile, GenderProfile
from .hybrid_tts_service import HybridTTSService
from .ssml_service import generate_ssml, normalize_arabic_text
from .tts_cache import get_cached_tts_audio, cache_tts_audio


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
    """Main TTS service with multi-dialect Arabic support.

    Features:
    - 32 Arabic voices across 16 dialects
    - Egyptian Arabic as default (ar-EG-SalmaNeural)
    - SSML generation with pronunciation lexicon
    - Phrase caching for performance
    - Hybrid provider architecture (Edge/Google/ElevenLabs)
    """

    def __init__(
        self,
        dialect: Optional[str] = None,
        gender: Optional[str] = None,
        use_cache: bool = True
    ):
        """Initialize TTS service with dialect support.

        Args:
            dialect: Dialect key (e.g., "arabic_egypt", "arabic_saudi")
                    Defaults to config setting (arabic_egypt)
            gender: Voice gender ("male" or "female")
                   Defaults to config setting (female)
            use_cache: Enable phrase caching (default: True)
        """
        settings = get_settings()
        self.settings = settings

        # Set dialect and gender
        self.dialect = dialect or settings.default_tts_dialect
        self.gender = gender or settings.default_tts_gender
        self.use_cache = use_cache

        # Get voice profile for selected dialect/gender
        self.voice_profile = get_voice_profile(self.dialect, self.gender)

        # Initialize hybrid TTS service
        self.hybrid_tts = HybridTTSService(
            use_google=settings.use_google_tts,
            use_elevenlabs=settings.use_elevenlabs_tts,
            google_credentials_path=settings.google_credentials_path if settings.google_credentials_path else None,
            elevenlabs_api_key=settings.elevenlabs_api_key if settings.elevenlabs_api_key else None
        )

        # Legacy engine support (for backward compatibility)
        self.engine = None
        if settings.tts_engine == "coqui":
            self.engine = CoquiTTSEngine()
            logger.info("TTS Service initialized with legacy Coqui engine")

        logger.info(
            f"✅ TTS Service initialized | "
            f"Dialect: {self.dialect} | "
            f"Gender: {self.gender} | "
            f"Voice: {self.voice_profile.voice_id} | "
            f"Cache: {self.use_cache}"
        )

    def update_voice(self, dialect: Optional[str] = None, gender: Optional[str] = None) -> None:
        """Update voice dialect/gender dynamically.

        Useful for real-time voice switching in conversations.

        Args:
            dialect: New dialect key (None to keep current)
            gender: New gender (None to keep current)
        """
        if dialect:
            self.dialect = dialect
        if gender:
            self.gender = gender

        # Reload voice profile
        self.voice_profile = get_voice_profile(self.dialect, self.gender)

        logger.info(
            f"Voice updated → {self.dialect} ({self.gender}): {self.voice_profile.voice_id}"
        )

    async def synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
        rate: Optional[str] = None,
        volume: Optional[str] = None,
        priority: str = "normal"
    ) -> tuple[bytes, float]:
        """Synthesize text to speech with dialect support.

        Args:
            text: Text to synthesize (plain or SSML)
            voice: Override voice ID (optional, defaults to profile)
            rate: Override speech rate (optional)
            volume: Override volume (optional)
            priority: Quality priority ("normal", "premium", "ultra")

        Returns:
            Tuple of (audio_data, processing_time_ms)
        """
        start_time = time.perf_counter()

        # Normalize text
        normalized_text = normalize_arabic_text(text)

        if not normalized_text.strip():
            logger.warning("Empty text after normalization")
            return b"", 0.0

        # Create voice profile override if needed
        if voice or rate or volume:
            voice_profile = GenderProfile(
                voice_id=voice or self.voice_profile.voice_id,
                display_name=self.voice_profile.display_name,
                rate=rate or self.voice_profile.rate,
                pitch=self.voice_profile.pitch,
                volume=volume or self.voice_profile.volume
            )
        else:
            voice_profile = self.voice_profile

        # Check cache first
        if self.use_cache:
            cached_audio = get_cached_tts_audio(
                normalized_text,
                voice_profile.voice_id,
                voice_profile.rate,
                voice_profile.pitch
            )

            if cached_audio:
                processing_time = (time.perf_counter() - start_time) * 1000
                logger.debug(
                    f"✓ Cache HIT ({processing_time:.1f}ms) | "
                    f"text: '{normalized_text[:50]}...'"
                )
                return cached_audio, processing_time

        # Use legacy engine if configured (Coqui)
        if self.engine:
            audio_data = await self.engine.synthesize(text, voice, rate, volume)
            processing_time = (time.perf_counter() - start_time) * 1000
            return audio_data, processing_time

        # Generate SSML if enabled
        if self.settings.use_ssml and not text.strip().startswith("<speak"):
            ssml_text = generate_ssml(
                normalized_text,
                voice_profile,
                self.dialect,
                use_lexicon=True
            )
            use_ssml = True
        else:
            ssml_text = normalized_text
            use_ssml = False

        # Synthesize using hybrid TTS
        audio_data = await self.hybrid_tts.synthesize(
            ssml_text,
            voice_profile,
            use_ssml=use_ssml,
            priority=priority
        )

        # Cache the result
        if self.use_cache and audio_data:
            cache_tts_audio(
                normalized_text,
                voice_profile.voice_id,
                voice_profile.rate,
                voice_profile.pitch,
                audio_data
            )

        processing_time = (time.perf_counter() - start_time) * 1000

        logger.debug(
            f"✓ TTS synthesized ({processing_time:.1f}ms) | "
            f"Voice: {voice_profile.voice_id} | "
            f"Size: {len(audio_data)} bytes | "
            f"Text: '{normalized_text[:50]}...'"
        )

        return audio_data, processing_time

    def get_current_voice_info(self) -> dict:
        """Get information about current voice configuration.

        Returns:
            Dictionary with dialect, gender, voice details
        """
        return {
            "dialect": self.dialect,
            "gender": self.gender,
            "voice_id": self.voice_profile.voice_id,
            "display_name": self.voice_profile.display_name,
            "rate": self.voice_profile.rate,
            "pitch": self.voice_profile.pitch,
            "volume": self.voice_profile.volume,
            "cache_enabled": self.use_cache
        }
