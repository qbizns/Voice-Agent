"""Hybrid TTS service with multiple provider support.

Supports multiple TTS providers with automatic fallback:
- Edge TTS (FREE, default)
- Google Cloud TTS (PREMIUM, optional)
- ElevenLabs (ULTRA-PREMIUM, optional)

Strategy:
- DEFAULT: Use Edge TTS (free, high quality, 32 Arabic voices)
- PREMIUM: Use Google TTS if available (better quality, fewer dialects)
- ULTRA: Use ElevenLabs if available (best quality, requires voice cloning)
"""

from typing import AsyncGenerator, Optional, Literal
from loguru import logger

from .voice_profiles import GenderProfile
from .edge_tts_service import EdgeTTSService


class HybridTTSService:
    """Hybrid TTS with multiple providers (Edge/Google/ElevenLabs).

    Currently implements Edge TTS with architecture for future premium providers.
    """

    def __init__(
        self,
        use_google: bool = False,
        use_elevenlabs: bool = False,
        google_credentials_path: Optional[str] = None,
        elevenlabs_api_key: Optional[str] = None
    ):
        """Initialize hybrid TTS service.

        Args:
            use_google: Enable Google TTS (not yet implemented)
            use_elevenlabs: Enable ElevenLabs (not yet implemented)
            google_credentials_path: Path to Google credentials JSON
            elevenlabs_api_key: ElevenLabs API key
        """
        # Always initialize Edge TTS (free fallback)
        self.edge_tts = EdgeTTSService()

        # Premium providers (to be implemented)
        self.google_tts = None
        self.elevenlabs_tts = None

        if use_google:
            logger.warning("Google TTS not yet implemented - using Edge TTS only")
            # TODO: Initialize GoogleTTSService when implemented

        if use_elevenlabs:
            logger.warning("ElevenLabs TTS not yet implemented - using Edge TTS only")
            # TODO: Initialize ElevenLabsService when implemented

        logger.info("✅ Hybrid TTS service initialized (Edge TTS active)")

    def _select_provider(
        self,
        priority: Literal["normal", "premium", "ultra"] = "normal"
    ) -> str:
        """Select TTS provider based on priority.

        Args:
            priority: Request priority level

        Returns:
            Provider name ("edge", "google", "elevenlabs")
        """
        # For now, always use Edge TTS
        # TODO: Add logic for premium providers when implemented

        if priority == "ultra" and self.elevenlabs_tts:
            return "elevenlabs"

        if priority in ["premium", "ultra"] and self.google_tts:
            return "google"

        return "edge"

    async def synthesize(
        self,
        text: str,
        voice_profile: GenderProfile,
        use_ssml: bool = False,
        priority: Literal["normal", "premium", "ultra"] = "normal"
    ) -> bytes:
        """Synthesize audio using selected provider.

        Args:
            text: Text to synthesize
            voice_profile: Voice configuration
            use_ssml: Whether text is SSML
            priority: Quality priority

        Returns:
            Audio data bytes (MP3 format)
        """
        provider = self._select_provider(priority)

        try:
            if provider == "elevenlabs" and self.elevenlabs_tts:
                logger.debug("Using ElevenLabs TTS (ultra)")
                return await self.elevenlabs_tts.synthesize(text, voice_profile, use_ssml)

            elif provider == "google" and self.google_tts:
                logger.debug("Using Google TTS (premium)")
                return await self.google_tts.synthesize(text, voice_profile, use_ssml)

            else:
                # Use Edge TTS (default)
                logger.debug("Using Edge TTS (free)")
                return await self.edge_tts.synthesize(text, voice_profile, use_ssml)

        except Exception as e:
            logger.error(f"{provider} TTS failed: {e}, falling back to Edge TTS")

            # Always fall back to Edge TTS on error
            if provider != "edge":
                return await self.edge_tts.synthesize(text, voice_profile, use_ssml)
            else:
                # Edge TTS itself failed
                raise

    async def synthesize_stream(
        self,
        text: str,
        voice_profile: GenderProfile,
        use_ssml: bool = False,
        priority: Literal["normal", "premium", "ultra"] = "normal",
        cancel_event: Optional = None
    ) -> AsyncGenerator[bytes, None]:
        """Synthesize audio as stream.

        Args:
            text: Text to synthesize
            voice_profile: Voice configuration
            use_ssml: Whether text is SSML
            priority: Quality priority
            cancel_event: Cancellation event

        Yields:
            Audio data chunks
        """
        provider = self._select_provider(priority)

        try:
            # Edge TTS has best streaming support
            if provider == "edge" or True:  # Always use Edge for streaming
                async for chunk in self.edge_tts.synthesize_stream(
                    text, voice_profile, use_ssml, cancel_event
                ):
                    yield chunk

            else:
                # Premium providers: generate full audio and yield as one chunk
                # (Google/ElevenLabs don't support true streaming)
                audio_data = await self.synthesize(text, voice_profile, use_ssml, priority)
                yield audio_data

        except Exception as e:
            logger.error(f"Streaming TTS error ({provider}): {e}")
            raise

    def get_provider_status(self) -> dict:
        """Get status of all TTS providers.

        Returns:
            Dictionary with provider availability
        """
        return {
            "edge": {
                "available": self.edge_tts is not None,
                "enabled": True,
                "cost": "free",
                "voices": 32
            },
            "google": {
                "available": self.google_tts is not None,
                "enabled": False,
                "cost": "premium",
                "voices": 0
            },
            "elevenlabs": {
                "available": self.elevenlabs_tts is not None,
                "enabled": False,
                "cost": "ultra-premium",
                "voices": 0
            }
        }
