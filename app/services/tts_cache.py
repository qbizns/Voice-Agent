"""In-memory cache for TTS phrases.

Caches generated audio to avoid redundant TTS calls for repeated phrases.
Uses LRU cache strategy with bounded memory.
"""

import hashlib
from typing import Optional, Dict
from loguru import logger
from .ssml_service import normalize_arabic_text


def generate_cache_key(
    text: str,
    voice_id: str,
    rate: str,
    pitch: str
) -> str:
    """Generate cache key for TTS request.

    Creates an MD5 hash from normalized text + voice parameters.

    Args:
        text: Text to synthesize
        voice_id: Voice ID
        rate: Speech rate
        pitch: Pitch adjustment

    Returns:
        MD5 hash as cache key
    """
    # Normalize text
    normalized = normalize_arabic_text(text)

    # Create composite key
    composite = f"{normalized}|{voice_id}|{rate}|{pitch}"

    # Hash it for consistent key length
    return hashlib.md5(composite.encode('utf-8')).hexdigest()


# Simple dict-based cache for runtime (bounded to 256 entries)
_audio_cache: Dict[str, bytes] = {}
_cache_max_size = 256


def cache_tts_audio(
    text: str,
    voice_id: str,
    rate: str,
    pitch: str,
    audio_data: bytes
) -> None:
    """Cache TTS audio data.

    Args:
        text: Text that was synthesized
        voice_id: Voice ID used
        rate: Speech rate
        pitch: Pitch adjustment
        audio_data: Generated audio bytes
    """
    cache_key = generate_cache_key(text, voice_id, rate, pitch)

    # Add to cache
    _audio_cache[cache_key] = audio_data

    logger.debug(
        f"✓ TTS cached (key={cache_key[:8]}..., size={len(audio_data)} bytes)"
    )

    # Enforce size limit (simple FIFO eviction)
    if len(_audio_cache) > _cache_max_size:
        # Remove oldest entry
        oldest_key = next(iter(_audio_cache))
        del _audio_cache[oldest_key]
        logger.debug(f"Cache full, evicted oldest entry (size={_cache_max_size})")


def get_cached_tts_audio(
    text: str,
    voice_id: str,
    rate: str,
    pitch: str
) -> Optional[bytes]:
    """Get cached TTS audio if available.

    Args:
        text: Text to synthesize
        voice_id: Voice ID
        rate: Speech rate
        pitch: Pitch adjustment

    Returns:
        Cached audio bytes or None if not cached
    """
    cache_key = generate_cache_key(text, voice_id, rate, pitch)
    audio_data = _audio_cache.get(cache_key)

    if audio_data:
        logger.debug(f"✓ TTS cache HIT (key={cache_key[:8]}...)")
    else:
        logger.debug(f"✗ TTS cache MISS (key={cache_key[:8]}...)")

    return audio_data


def clear_tts_cache() -> None:
    """Clear all cached TTS audio."""
    count = len(_audio_cache)
    _audio_cache.clear()
    logger.info(f"TTS cache cleared ({count} entries removed)")


def get_cache_stats() -> dict:
    """Get cache statistics.

    Returns:
        Dictionary with cache stats:
        - entries: Current number of cached phrases
        - max_entries: Maximum cache size
        - total_bytes: Total size of cached audio
        - avg_bytes_per_entry: Average audio size
    """
    total_bytes = sum(len(data) for data in _audio_cache.values())
    entry_count = len(_audio_cache)

    return {
        "entries": entry_count,
        "max_entries": _cache_max_size,
        "total_bytes": total_bytes,
        "avg_bytes_per_entry": total_bytes // entry_count if entry_count > 0 else 0,
        "utilization_percent": (entry_count / _cache_max_size) * 100
    }


def set_cache_max_size(size: int) -> None:
    """Change maximum cache size.

    Args:
        size: New maximum number of entries
    """
    global _cache_max_size
    old_size = _cache_max_size
    _cache_max_size = size

    # Evict excess entries if new size is smaller
    while len(_audio_cache) > _cache_max_size:
        oldest_key = next(iter(_audio_cache))
        del _audio_cache[oldest_key]

    logger.info(f"TTS cache size changed: {old_size} → {_cache_max_size}")


def is_cached(text: str, voice_id: str, rate: str, pitch: str) -> bool:
    """Check if audio is cached without retrieving it.

    Args:
        text: Text to check
        voice_id: Voice ID
        rate: Speech rate
        pitch: Pitch adjustment

    Returns:
        True if cached, False otherwise
    """
    cache_key = generate_cache_key(text, voice_id, rate, pitch)
    return cache_key in _audio_cache


# Pre-cache common system phrases (optional)
COMMON_PHRASES = [
    "مرحباً، كيف أقدر أساعدك؟",
    "ثانية واحدة من فضلك",
    "عذراً، لم أفهم",
    "هل يمكنك إعادة السؤال؟",
    "شكراً لك",
    "تم بنجاح",
]


async def precache_common_phrases(tts_service) -> None:
    """Pre-generate and cache common system phrases.

    This should be called at startup to warm up the cache.

    Args:
        tts_service: TTS service instance to use for generation
    """
    logger.info(f"Pre-caching {len(COMMON_PHRASES)} common phrases...")

    for phrase in COMMON_PHRASES:
        try:
            # Generate audio (will be automatically cached)
            await tts_service.synthesize(phrase)
        except Exception as e:
            logger.warning(f"Failed to pre-cache phrase '{phrase}': {e}")

    logger.info(f"✅ Pre-cached {len(COMMON_PHRASES)} phrases")
