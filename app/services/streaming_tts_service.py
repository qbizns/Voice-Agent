"""Streaming Text-to-Speech service with sentence chunking and dialect support.

Generates audio in chunks (sentence-by-sentence) for streaming playback,
dramatically reducing perceived latency.

Features:
- 32 Arabic voices across 16 dialects
- Egyptian Arabic as default
- SSML generation with pronunciation lexicon
- Sentence-level chunking for low latency
- Hybrid provider architecture
"""

import re
import asyncio
from typing import AsyncGenerator, List, Optional
from loguru import logger

from app.core.config import get_settings
from .voice_profiles import get_voice_profile, GenderProfile
from .hybrid_tts_service import HybridTTSService
from .ssml_service import generate_ssml, normalize_arabic_text
from .tts_cache import get_cached_tts_audio, cache_tts_audio


class StreamingTTSService:
    """Streaming TTS service with sentence-level chunking and dialect support."""

    def __init__(
        self,
        dialect: Optional[str] = None,
        gender: Optional[str] = None,
        min_chunk_chars: int = 20,
        max_chunk_chars: int = 200,
        use_cache: bool = True
    ):
        """Initialize streaming TTS service with dialect support.

        Args:
            dialect: Dialect key (e.g., "arabic_egypt", "arabic_saudi")
                    Defaults to config setting (arabic_egypt)
            gender: Voice gender ("male" or "female")
                   Defaults to config setting (female)
            min_chunk_chars: Minimum characters before sending chunk
            max_chunk_chars: Maximum characters per chunk
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

        # Chunking settings
        self.min_chunk_chars = min_chunk_chars
        self.max_chunk_chars = max_chunk_chars

        logger.info(
            f"✅ Streaming TTS initialized | "
            f"Dialect: {self.dialect} | "
            f"Gender: {self.gender} | "
            f"Voice: {self.voice_profile.voice_id} | "
            f"Min/Max chunk: {min_chunk_chars}/{max_chunk_chars}"
        )

    def update_voice(self, dialect: Optional[str] = None, gender: Optional[str] = None) -> None:
        """Update voice dialect/gender dynamically.

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

    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences for streaming.

        Supports both Arabic and English sentence boundaries.

        Args:
            text: Input text

        Returns:
            List of sentence strings
        """
        if not text or not text.strip():
            return []

        # Arabic and English sentence delimiters
        # Arabic: ؟ (question mark), ۔ (full stop), ! (exclamation)
        # English: . ? !
        # Also handle line breaks as sentence boundaries

        # First, normalize line breaks
        text = text.replace('\r\n', '\n').replace('\r', '\n')

        # Split by common sentence delimiters
        # Use lookahead to keep the delimiter with the sentence
        pattern = r'([.!؟۔]\s+|\n+)'

        parts = re.split(pattern, text)

        sentences = []
        current = ""

        for i, part in enumerate(parts):
            if not part or part.isspace():
                continue

            # If this is a delimiter, attach to current sentence
            if re.match(r'^[.!؟۔]\s*$|^\n+$', part):
                current += part.strip() + " "
                if current.strip():
                    sentences.append(current.strip())
                    current = ""
            else:
                current += part

        # Add any remaining text
        if current.strip():
            sentences.append(current.strip())

        # Post-process: merge very short sentences
        merged = []
        buffer = ""

        for sentence in sentences:
            if len(buffer) + len(sentence) < self.min_chunk_chars:
                buffer += " " + sentence if buffer else sentence
            else:
                if buffer:
                    merged.append(buffer)
                buffer = sentence

        if buffer:
            merged.append(buffer)

        # Split sentences that are too long
        final_sentences = []
        for sentence in merged:
            if len(sentence) <= self.max_chunk_chars:
                final_sentences.append(sentence)
            else:
                # Split long sentences at commas or spaces
                chunks = self._split_long_sentence(sentence)
                final_sentences.extend(chunks)

        logger.debug(f"Split text into {len(final_sentences)} chunks: {[s[:30]+'...' if len(s) > 30 else s for s in final_sentences]}")

        return final_sentences

    def _split_long_sentence(self, sentence: str) -> List[str]:
        """Split a long sentence into smaller chunks.

        Args:
            sentence: Long sentence to split

        Returns:
            List of chunks
        """
        # Try to split at commas first
        if '،' in sentence or ',' in sentence:
            parts = re.split(r'[،,]\s*', sentence)
            chunks = []
            current = ""

            for part in parts:
                if len(current) + len(part) <= self.max_chunk_chars:
                    current += (", " if current else "") + part
                else:
                    if current:
                        chunks.append(current)
                    current = part

            if current:
                chunks.append(current)

            return chunks

        # Fall back to splitting at spaces
        words = sentence.split()
        chunks = []
        current = ""

        for word in words:
            if len(current) + len(word) + 1 <= self.max_chunk_chars:
                current += (" " if current else "") + word
            else:
                if current:
                    chunks.append(current)
                current = word

        if current:
            chunks.append(current)

        return chunks if chunks else [sentence]

    async def synthesize_stream(
        self,
        text: str,
        cancel_event: Optional[asyncio.Event] = None,
        priority: str = "normal"
    ) -> AsyncGenerator[bytes, None]:
        """Generate audio stream in sentence-level chunks with dialect support.

        Args:
            text: Text to synthesize
            cancel_event: Optional event to signal cancellation
            priority: Quality priority ("normal", "premium", "ultra")

        Yields:
            Audio data chunks (MP3 format)
        """
        # Normalize text
        normalized_text = normalize_arabic_text(text)

        if not normalized_text.strip():
            logger.warning("Empty text after normalization")
            return

        # Split text into sentences
        sentences = self._split_into_sentences(normalized_text)

        if not sentences:
            logger.warning("No sentences extracted from text")
            return

        logger.info(
            f"Streaming TTS: {len(sentences)} chunks | "
            f"Voice: {self.voice_profile.voice_id} | "
            f"Dialect: {self.dialect}"
        )

        # Generate audio for each sentence
        for i, sentence in enumerate(sentences):
            # Check for cancellation
            if cancel_event and cancel_event.is_set():
                logger.info(f"Streaming TTS cancelled at chunk {i+1}/{len(sentences)}")
                return

            try:
                logger.debug(f"Chunk {i+1}/{len(sentences)}: '{sentence[:50]}...'")

                # Check cache first (for common phrases)
                chunk_data = None
                if self.use_cache:
                    chunk_data = get_cached_tts_audio(
                        sentence,
                        self.voice_profile.voice_id,
                        self.voice_profile.rate,
                        self.voice_profile.pitch
                    )

                if not chunk_data:
                    # Generate SSML if enabled
                    if self.settings.use_ssml and not sentence.strip().startswith("<speak"):
                        ssml_text = generate_ssml(
                            sentence,
                            self.voice_profile,
                            self.dialect,
                            use_lexicon=True
                        )
                        use_ssml = True
                    else:
                        ssml_text = sentence
                        use_ssml = False

                    # Synthesize using hybrid TTS streaming
                    chunk_data = b""
                    async for audio_chunk in self.hybrid_tts.synthesize_stream(
                        ssml_text,
                        self.voice_profile,
                        use_ssml=use_ssml,
                        priority=priority,
                        cancel_event=cancel_event
                    ):
                        chunk_data += audio_chunk

                        # Check for cancellation during generation
                        if cancel_event and cancel_event.is_set():
                            logger.info(f"Streaming TTS cancelled during chunk {i+1}/{len(sentences)}")
                            return

                    # Cache the result
                    if self.use_cache and chunk_data:
                        cache_tts_audio(
                            sentence,
                            self.voice_profile.voice_id,
                            self.voice_profile.rate,
                            self.voice_profile.pitch,
                            chunk_data
                        )

                # Yield complete sentence audio
                if chunk_data:
                    logger.debug(f"✓ Yielding chunk {i+1}/{len(sentences)} ({len(chunk_data)} bytes)")
                    yield chunk_data
                else:
                    logger.warning(f"No audio generated for chunk {i+1}: '{sentence}'")

            except Exception as e:
                logger.error(f"Error generating chunk {i+1}/{len(sentences)}: {e}")
                # Continue with next sentence even if one fails
                continue

        logger.info(f"✅ Streaming TTS completed ({len(sentences)} chunks)")

    async def synthesize_full(
        self,
        text: str,
        priority: str = "normal"
    ) -> Optional[bytes]:
        """Generate complete audio (non-streaming fallback).

        Args:
            text: Text to synthesize
            priority: Quality priority ("normal", "premium", "ultra")

        Returns:
            Complete audio data or None on error
        """
        # Normalize text
        normalized_text = normalize_arabic_text(text)

        if not normalized_text.strip():
            logger.warning("Empty text after normalization")
            return None

        try:
            logger.info(f"Generating full audio | Voice: {self.voice_profile.voice_id}")

            # Check cache first
            if self.use_cache:
                cached_audio = get_cached_tts_audio(
                    normalized_text,
                    self.voice_profile.voice_id,
                    self.voice_profile.rate,
                    self.voice_profile.pitch
                )

                if cached_audio:
                    logger.debug(f"✓ Cache HIT for full audio")
                    return cached_audio

            # Generate SSML if enabled
            if self.settings.use_ssml and not normalized_text.strip().startswith("<speak"):
                ssml_text = generate_ssml(
                    normalized_text,
                    self.voice_profile,
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
                self.voice_profile,
                use_ssml=use_ssml,
                priority=priority
            )

            # Cache the result
            if self.use_cache and audio_data:
                cache_tts_audio(
                    normalized_text,
                    self.voice_profile.voice_id,
                    self.voice_profile.rate,
                    self.voice_profile.pitch,
                    audio_data
                )

            logger.info(f"✅ Generated full audio ({len(audio_data)} bytes)")
            return audio_data

        except Exception as e:
            logger.error(f"Error generating full audio: {e}")
            return None

    def get_config(self) -> dict:
        """Get current configuration.

        Returns:
            Configuration dictionary with dialect support
        """
        return {
            "dialect": self.dialect,
            "gender": self.gender,
            "voice_id": self.voice_profile.voice_id,
            "display_name": self.voice_profile.display_name,
            "rate": self.voice_profile.rate,
            "pitch": self.voice_profile.pitch,
            "volume": self.voice_profile.volume,
            "min_chunk_chars": self.min_chunk_chars,
            "max_chunk_chars": self.max_chunk_chars,
            "cache_enabled": self.use_cache,
            "ssml_enabled": self.settings.use_ssml
        }
