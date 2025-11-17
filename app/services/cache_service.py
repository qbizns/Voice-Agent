"""Intelligent response caching service with semantic similarity matching.

Caches responses for frequently asked questions and provides fast retrieval
using both exact matching and semantic similarity.
"""

import time
import hashlib
import json
from typing import Optional, Dict, Tuple, List
from dataclasses import dataclass, field
from loguru import logger

import numpy as np


@dataclass
class CacheEntry:
    """Represents a cached response."""
    query: str
    query_normalized: str
    response_text: str
    audio_data: bytes
    audio_format: str  # e.g., "mp3", "wav"
    sources: Optional[List[str]] = None
    hits: int = 0
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    ttl_seconds: Optional[int] = None  # None = permanent
    metadata: Dict = field(default_factory=dict)

    def is_expired(self) -> bool:
        """Check if cache entry is expired."""
        if self.ttl_seconds is None:
            return False
        return (time.time() - self.created_at) > self.ttl_seconds

    def access(self) -> None:
        """Record access to this entry."""
        self.hits += 1
        self.last_accessed = time.time()

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "query": self.query,
            "response_text": self.response_text,
            "audio_format": self.audio_format,
            "sources": self.sources,
            "hits": self.hits,
            "created_at": self.created_at,
            "last_accessed": self.last_accessed,
            "ttl_seconds": self.ttl_seconds,
            "age_seconds": time.time() - self.created_at
        }


class ResponseCache:
    """Response caching with exact and semantic matching."""

    def __init__(
        self,
        max_entries: int = 1000,
        default_ttl_seconds: Optional[int] = 3600,  # 1 hour
        similarity_threshold: float = 0.85
    ):
        """Initialize cache.

        Args:
            max_entries: Maximum number of cache entries
            default_ttl_seconds: Default TTL for cache entries (None = permanent)
            similarity_threshold: Minimum similarity score for semantic matching
        """
        self.max_entries = max_entries
        self.default_ttl = default_ttl_seconds
        self.similarity_threshold = similarity_threshold

        # Cache storage
        self.exact_cache: Dict[str, CacheEntry] = {}  # hash -> entry
        self.entries: List[CacheEntry] = []  # All entries for similarity search

        # Embeddings for semantic search (optional)
        self.embeddings: Optional[np.ndarray] = None
        self.embedding_model = None

        # Statistics
        self.total_hits = 0
        self.total_misses = 0

        # Embedding model will be loaded lazily on first use
        logger.info(f"Response cache initialized (max={max_entries}, threshold={similarity_threshold}, semantic search will load on first use)")

    def _init_embedding_model(self):
        """Initialize embedding model for semantic search (lazy loading)."""
        if self.embedding_model is not None:
            return
            
        try:
            from sentence_transformers import SentenceTransformer

            # Use a lightweight multilingual model
            logger.info("Loading embedding model for semantic search...")
            self.embedding_model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
            logger.info("Semantic search enabled with SentenceTransformer")

        except ImportError:
            logger.warning("SentenceTransformer not available - semantic search disabled")
            logger.warning("Install with: pip install sentence-transformers")
        except Exception as e:
            logger.warning(f"Failed to load embedding model: {e}")

    def _normalize_query(self, query: str) -> str:
        """Normalize query for better matching.

        Args:
            query: Input query

        Returns:
            Normalized query
        """
        # Convert to lowercase
        normalized = query.lower().strip()

        # Remove extra whitespace
        normalized = " ".join(normalized.split())

        # Remove common Arabic diacritics
        arabic_diacritics = "ًٌٍَُِّْ"
        for diacritic in arabic_diacritics:
            normalized = normalized.replace(diacritic, "")

        # Remove question marks and common punctuation
        normalized = normalized.replace("؟", "").replace("?", "").replace(".", "").replace("،", "")

        return normalized.strip()

    def _get_query_hash(self, query_normalized: str) -> str:
        """Get hash for normalized query.

        Args:
            query_normalized: Normalized query

        Returns:
            Hash string
        """
        return hashlib.md5(query_normalized.encode('utf-8')).hexdigest()

    def get(
        self,
        query: str,
        use_semantic: bool = True
    ) -> Optional[Tuple[str, bytes, Optional[List[str]]]]:
        """Get cached response for query.

        Args:
            query: User query
            use_semantic: Enable semantic similarity matching

        Returns:
            Tuple of (response_text, audio_data, sources) or None if not found
        """
        # Normalize query
        query_normalized = self._normalize_query(query)
        query_hash = self._get_query_hash(query_normalized)

        # Try exact match first
        if query_hash in self.exact_cache:
            entry = self.exact_cache[query_hash]

            # Check if expired
            if entry.is_expired():
                logger.debug(f"Cache entry expired: {query_normalized}")
                self._remove_entry(query_hash)
                self.total_misses += 1
                return None

            # Return cached response
            entry.access()
            self.total_hits += 1
            logger.info(f"Cache HIT (exact): '{query}' (hits={entry.hits})")
            return entry.response_text, entry.audio_data, entry.sources

        # Try semantic matching if enabled (lazy load model if needed)
        if use_semantic and len(self.entries) > 0:
            self._init_embedding_model()  # Lazy load if needed
        if use_semantic and self.embedding_model and len(self.entries) > 0:
            match = self._semantic_search(query_normalized)
            if match:
                entry, similarity = match
                entry.access()
                self.total_hits += 1
                logger.info(f"Cache HIT (semantic, similarity={similarity:.2f}): '{query}' -> '{entry.query}' (hits={entry.hits})")
                return entry.response_text, entry.audio_data, entry.sources

        # Cache miss
        self.total_misses += 1
        logger.debug(f"Cache MISS: '{query}'")
        return None

    def put(
        self,
        query: str,
        response_text: str,
        audio_data: bytes,
        audio_format: str = "mp3",
        sources: Optional[List[str]] = None,
        ttl_seconds: Optional[int] = None,
        metadata: Optional[Dict] = None
    ) -> None:
        """Add response to cache.

        Args:
            query: User query
            response_text: Response text
            audio_data: Audio response data
            audio_format: Audio format
            sources: Optional source references
            ttl_seconds: Time to live (None for default, -1 for permanent)
            metadata: Optional metadata
        """
        # Normalize query
        query_normalized = self._normalize_query(query)
        query_hash = self._get_query_hash(query_normalized)

        # Use default TTL if not specified
        if ttl_seconds is None:
            ttl_seconds = self.default_ttl
        elif ttl_seconds == -1:
            ttl_seconds = None  # Permanent

        # Create cache entry
        entry = CacheEntry(
            query=query,
            query_normalized=query_normalized,
            response_text=response_text,
            audio_data=audio_data,
            audio_format=audio_format,
            sources=sources,
            ttl_seconds=ttl_seconds,
            metadata=metadata or {}
        )

        # Check if we need to evict entries (LRU)
        if len(self.exact_cache) >= self.max_entries:
            self._evict_lru()

        # Add to exact cache
        self.exact_cache[query_hash] = entry
        self.entries.append(entry)

        # Update embeddings for semantic search
        if self.embedding_model:
            self._update_embeddings()

        logger.info(f"Cached response: '{query}' (total_entries={len(self.entries)})")

    def _semantic_search(
        self,
        query_normalized: str
    ) -> Optional[Tuple[CacheEntry, float]]:
        """Search for semantically similar cached queries.

        Args:
            query_normalized: Normalized query

        Returns:
            Tuple of (entry, similarity_score) or None
        """
        if not self.embedding_model or not self.embeddings is not None or len(self.entries) == 0:
            return None

        try:
            # Encode query
            query_embedding = self.embedding_model.encode([query_normalized])[0]

            # Compute cosine similarities
            similarities = np.dot(self.embeddings, query_embedding) / (
                np.linalg.norm(self.embeddings, axis=1) * np.linalg.norm(query_embedding)
            )

            # Find best match above threshold
            best_idx = np.argmax(similarities)
            best_score = similarities[best_idx]

            if best_score >= self.similarity_threshold:
                entry = self.entries[best_idx]

                # Check if entry is expired
                if not entry.is_expired():
                    return entry, float(best_score)

        except Exception as e:
            logger.error(f"Error in semantic search: {e}")

        return None

    def _update_embeddings(self) -> None:
        """Update embedding matrix for semantic search."""
        if not self.embedding_model or len(self.entries) == 0:
            return

        try:
            # Get all normalized queries
            queries = [entry.query_normalized for entry in self.entries]

            # Encode all queries
            self.embeddings = self.embedding_model.encode(queries)
            logger.debug(f"Updated embeddings for {len(queries)} entries")

        except Exception as e:
            logger.error(f"Failed to update embeddings: {e}")

    def _evict_lru(self) -> None:
        """Evict least recently used entry."""
        if not self.entries:
            return

        # Find LRU entry
        lru_entry = min(self.entries, key=lambda e: e.last_accessed)

        # Remove from exact cache
        query_hash = self._get_query_hash(lru_entry.query_normalized)
        if query_hash in self.exact_cache:
            del self.exact_cache[query_hash]

        # Remove from entries list
        self.entries.remove(lru_entry)

        # Rebuild embeddings
        if self.embedding_model:
            self._update_embeddings()

        logger.debug(f"Evicted LRU entry: '{lru_entry.query}' (hits={lru_entry.hits})")

    def _remove_entry(self, query_hash: str) -> None:
        """Remove entry by hash."""
        if query_hash in self.exact_cache:
            entry = self.exact_cache[query_hash]
            del self.exact_cache[query_hash]

            if entry in self.entries:
                self.entries.remove(entry)

            # Rebuild embeddings
            if self.embedding_model:
                self._update_embeddings()

    def clear(self) -> None:
        """Clear all cache entries."""
        self.exact_cache.clear()
        self.entries.clear()
        self.embeddings = None
        logger.info("Cache cleared")

    def get_stats(self) -> Dict:
        """Get cache statistics.

        Returns:
            Statistics dictionary
        """
        total_requests = self.total_hits + self.total_misses
        hit_rate = self.total_hits / total_requests if total_requests > 0 else 0.0

        return {
            "total_entries": len(self.entries),
            "total_hits": self.total_hits,
            "total_misses": self.total_misses,
            "hit_rate": hit_rate,
            "semantic_enabled": self.embedding_model is not None,
            "entries": [entry.to_dict() for entry in sorted(self.entries, key=lambda e: e.hits, reverse=True)[:10]]
        }

    def prewarm(self, faqs: List[Tuple[str, str]]) -> None:
        """Pre-warm cache with FAQ entries.

        Args:
            faqs: List of (question, answer) tuples
        """
        logger.info(f"Pre-warming cache with {len(faqs)} FAQ entries...")

        for question, answer in faqs:
            # For FAQs, we don't have audio - will be generated on first real request
            # But we can cache the text response
            self.put(
                query=question,
                response_text=answer,
                audio_data=b"",  # Empty audio
                audio_format="none",
                ttl_seconds=-1,  # Permanent
                metadata={"type": "faq", "prewarmed": True}
            )

        logger.info(f"Cache pre-warmed with {len(faqs)} FAQs")
