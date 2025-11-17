"""Base TTS service interface using Protocol for type checking.

All TTS providers (Edge, Google, ElevenLabs) must implement this interface.
"""

from typing import Protocol, AsyncGenerator, runtime_checkable
from .voice_profiles import GenderProfile


@runtime_checkable
class BaseTTSService(Protocol):
    """Protocol for TTS service implementations.

    All TTS providers must implement these methods to be compatible
    with the HybridTTSService.
    """

    async def synthesize(
        self,
        text: str,
        voice_profile: GenderProfile,
        use_ssml: bool = False
    ) -> bytes:
        """Synthesize text to speech.

        Args:
            text: Text to synthesize (plain text or SSML)
            voice_profile: Voice configuration
            use_ssml: Whether text contains SSML markup

        Returns:
            Audio data bytes (format depends on provider, typically MP3)
        """
        ...

    async def synthesize_stream(
        self,
        text: str,
        voice_profile: GenderProfile,
        use_ssml: bool = False
    ) -> AsyncGenerator[bytes, None]:
        """Synthesize text to speech as a stream.

        Args:
            text: Text to synthesize
            voice_profile: Voice configuration
            use_ssml: Whether text contains SSML markup

        Yields:
            Audio data chunks
        """
        ...
