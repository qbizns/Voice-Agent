"""Edge TTS service implementation (FREE Microsoft TTS).

Microsoft Edge TTS provides high-quality neural voices for free.
No API key required, no rate limits.
"""

import asyncio
from typing import AsyncGenerator, Optional
from loguru import logger

try:
    import edge_tts
    EDGE_TTS_AVAILABLE = True
except ImportError:
    EDGE_TTS_AVAILABLE = False
    logger.warning("edge-tts package not available - install with: pip install edge-tts")

from .voice_profiles import GenderProfile


class EdgeTTSService:
    """Microsoft Edge TTS service (FREE).

    Provides access to 32 Arabic neural voices across 16 dialects.
    Default: Egyptian Arabic (ar-EG-SalmaNeural).
    """

    def __init__(self):
        """Initialize Edge TTS service.

        Raises:
            ImportError: If edge-tts package not installed
        """
        if not EDGE_TTS_AVAILABLE:
            raise ImportError(
                "edge-tts package not installed. Install with: pip install edge-tts"
            )

        self.enabled = True
        logger.info("✅ Edge TTS service initialized (FREE - no API key required)")

    async def synthesize(
        self,
        text: str,
        voice_profile: GenderProfile,
        use_ssml: bool = False
    ) -> bytes:
        """Synthesize complete audio.

        Args:
            text: Text or SSML to synthesize
            voice_profile: Voice configuration
            use_ssml: Whether text is SSML (Edge TTS auto-detects)

        Returns:
            Complete audio data (MP3 format)
        """
        if not text or not text.strip():
            logger.warning("Empty text provided for TTS")
            return b""

        try:
            logger.debug(
                f"Edge TTS: {voice_profile.voice_id} | "
                f"rate={voice_profile.rate} pitch={voice_profile.pitch} | "
                f"text='{text[:50]}...'"
            )

            # Create Edge TTS communicate object
            communicate = edge_tts.Communicate(
                text=text,
                voice=voice_profile.voice_id,
                rate=voice_profile.rate,
                volume=voice_profile.volume,
                pitch=voice_profile.pitch
            )

            # Collect all audio chunks
            audio_data = b""
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_data += chunk["data"]

            logger.debug(f"Edge TTS generated {len(audio_data)} bytes")
            return audio_data

        except Exception as e:
            logger.error(f"Edge TTS synthesis error: {e}")
            raise RuntimeError(f"Edge TTS failed: {e}")

    async def synthesize_stream(
        self,
        text: str,
        voice_profile: GenderProfile,
        use_ssml: bool = False,
        cancel_event: Optional[asyncio.Event] = None
    ) -> AsyncGenerator[bytes, None]:
        """Synthesize audio as stream.

        Yields audio chunks as they're generated for low-latency playback.

        Args:
            text: Text or SSML to synthesize
            voice_profile: Voice configuration
            use_ssml: Whether text is SSML
            cancel_event: Optional cancellation event

        Yields:
            Audio data chunks (MP3)
        """
        if not text or not text.strip():
            return

        try:
            logger.debug(
                f"Edge TTS streaming: {voice_profile.voice_id} | "
                f"text='{text[:50]}...'"
            )

            # Create Edge TTS communicate object
            communicate = edge_tts.Communicate(
                text=text,
                voice=voice_profile.voice_id,
                rate=voice_profile.rate,
                volume=voice_profile.volume,
                pitch=voice_profile.pitch
            )

            chunk_count = 0

            # Stream audio chunks
            async for chunk in communicate.stream():
                # Check for cancellation
                if cancel_event and cancel_event.is_set():
                    logger.info("Edge TTS streaming cancelled")
                    return

                if chunk["type"] == "audio":
                    chunk_count += 1
                    yield chunk["data"]

            logger.debug(f"Edge TTS streamed {chunk_count} chunks")

        except Exception as e:
            logger.error(f"Edge TTS streaming error: {e}")
            raise RuntimeError(f"Edge TTS streaming failed: {e}")

    async def test_voice(self, voice_id: str, sample_text: str = "مرحباً") -> bytes:
        """Test a specific voice with sample text.

        Useful for voice preview functionality.

        Args:
            voice_id: Edge TTS voice ID
            sample_text: Text to synthesize

        Returns:
            Audio data bytes
        """
        from .voice_profiles import GenderProfile

        # Create temporary profile
        temp_profile = GenderProfile(
            voice_id=voice_id,
            display_name="Test",
            rate="+0%",
            pitch="+0Hz",
            volume="+0%"
        )

        return await self.synthesize(sample_text, temp_profile)
