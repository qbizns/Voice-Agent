"""Streaming Text-to-Speech service with sentence chunking.

Generates audio in chunks (sentence-by-sentence) for streaming playback,
dramatically reducing perceived latency.
"""

import re
import asyncio
from typing import AsyncGenerator, List, Optional
from loguru import logger

try:
    import edge_tts
    EDGE_TTS_AVAILABLE = True
except ImportError:
    EDGE_TTS_AVAILABLE = False
    logger.warning("edge-tts not available - streaming TTS disabled")


class StreamingTTSService:
    """Streaming TTS service with sentence-level chunking."""

    def __init__(
        self,
        voice: str = "ar-SA-ZariyahNeural",
        rate: str = "+0%",
        volume: str = "+0%",
        min_chunk_chars: int = 20,
        max_chunk_chars: int = 200
    ):
        """Initialize streaming TTS service.

        Args:
            voice: Edge TTS voice ID
            rate: Speech rate adjustment
            volume: Volume adjustment
            min_chunk_chars: Minimum characters before sending chunk
            max_chunk_chars: Maximum characters per chunk
        """
        self.voice = voice
        self.rate = rate
        self.volume = volume
        self.min_chunk_chars = min_chunk_chars
        self.max_chunk_chars = max_chunk_chars
        self.enabled = EDGE_TTS_AVAILABLE

        if self.enabled:
            logger.info(f"Streaming TTS initialized (voice={voice}, min_chunk={min_chunk_chars})")
        else:
            logger.warning("Streaming TTS disabled (edge-tts not available)")

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
        cancel_event: Optional[asyncio.Event] = None
    ) -> AsyncGenerator[bytes, None]:
        """Generate audio stream in sentence-level chunks.

        Args:
            text: Text to synthesize
            cancel_event: Optional event to signal cancellation

        Yields:
            Audio data chunks (MP3 format)
        """
        if not self.enabled:
            logger.error("Streaming TTS not available")
            return

        if not text or not text.strip():
            logger.warning("Empty text provided for TTS")
            return

        # Split text into sentences
        sentences = self._split_into_sentences(text)

        if not sentences:
            logger.warning("No sentences extracted from text")
            return

        logger.info(f"Streaming TTS for {len(sentences)} chunks")

        # Generate audio for each sentence
        for i, sentence in enumerate(sentences):
            # Check for cancellation
            if cancel_event and cancel_event.is_set():
                logger.info(f"Streaming TTS cancelled at chunk {i+1}/{len(sentences)}")
                return

            try:
                logger.debug(f"Generating chunk {i+1}/{len(sentences)}: '{sentence[:50]}...'")

                # Use Edge TTS to generate audio for this sentence
                communicate = edge_tts.Communicate(
                    text=sentence,
                    voice=self.voice,
                    rate=self.rate,
                    volume=self.volume
                )

                # Collect all audio data for this sentence
                chunk_data = b""
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        chunk_data += chunk["data"]

                    # Check for cancellation during generation
                    if cancel_event and cancel_event.is_set():
                        logger.info(f"Streaming TTS cancelled during chunk {i+1}/{len(sentences)}")
                        return

                # Yield complete sentence audio
                if chunk_data:
                    logger.debug(f"Yielding chunk {i+1}/{len(sentences)} ({len(chunk_data)} bytes)")
                    yield chunk_data
                else:
                    logger.warning(f"No audio generated for chunk {i+1}: '{sentence}'")

            except Exception as e:
                logger.error(f"Error generating chunk {i+1}/{len(sentences)}: {e}")
                # Continue with next sentence even if one fails
                continue

        logger.info(f"Streaming TTS completed ({len(sentences)} chunks)")

    async def synthesize_full(self, text: str) -> Optional[bytes]:
        """Generate complete audio (non-streaming fallback).

        Args:
            text: Text to synthesize

        Returns:
            Complete audio data or None on error
        """
        if not self.enabled:
            logger.error("Streaming TTS not available")
            return None

        if not text or not text.strip():
            logger.warning("Empty text provided for TTS")
            return None

        try:
            logger.info("Generating full audio (non-streaming)")

            communicate = edge_tts.Communicate(
                text=text,
                voice=self.voice,
                rate=self.rate,
                volume=self.volume
            )

            audio_data = b""
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_data += chunk["data"]

            logger.info(f"Generated full audio ({len(audio_data)} bytes)")
            return audio_data

        except Exception as e:
            logger.error(f"Error generating full audio: {e}")
            return None

    def get_config(self) -> dict:
        """Get current configuration.

        Returns:
            Configuration dictionary
        """
        return {
            "enabled": self.enabled,
            "voice": self.voice,
            "rate": self.rate,
            "volume": self.volume,
            "min_chunk_chars": self.min_chunk_chars,
            "max_chunk_chars": self.max_chunk_chars
        }
