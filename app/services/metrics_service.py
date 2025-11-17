"""Metrics collection and monitoring service.

Collects and aggregates system metrics for monitoring and analytics.
"""

import time
import asyncio
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from collections import deque
from loguru import logger


@dataclass
class RequestMetrics:
    """Metrics for a single request."""
    timestamp: float
    session_id: str
    stt_time_ms: float
    ai_time_ms: float
    tts_time_ms: float
    total_time_ms: float
    success: bool
    error_message: Optional[str] = None
    cache_hit: bool = False
    streaming: bool = False
    text_length: int = 0


@dataclass
class SessionMetrics:
    """Metrics for a session."""
    session_id: str
    start_time: float
    end_time: Optional[float] = None
    request_count: int = 0
    total_processing_time_ms: float = 0.0
    errors: int = 0
    cache_hits: int = 0


class MetricsService:
    """Service for collecting and aggregating metrics."""

    def __init__(
        self,
        max_request_history: int = 1000,
        aggregation_window_seconds: int = 60
    ):
        """Initialize metrics service.

        Args:
            max_request_history: Maximum number of requests to keep in history
            aggregation_window_seconds: Time window for aggregated metrics
        """
        self.max_request_history = max_request_history
        self.aggregation_window = aggregation_window_seconds

        # Request metrics
        self.request_history: deque[RequestMetrics] = deque(maxlen=max_request_history)

        # Session tracking
        self.active_sessions: Dict[str, SessionMetrics] = {}
        self.session_history: deque[SessionMetrics] = deque(maxlen=100)

        # Counters
        self.total_requests = 0
        self.total_errors = 0
        self.total_cache_hits = 0
        self.total_streaming_requests = 0

        # Timing stats
        self.total_stt_time_ms = 0.0
        self.total_ai_time_ms = 0.0
        self.total_tts_time_ms = 0.0
        self.total_processing_time_ms = 0.0

        # Service start time
        self.start_time = time.time()

        logger.info(f"Metrics service initialized (history={max_request_history})")

    def record_request(
        self,
        session_id: str,
        stt_time_ms: float,
        ai_time_ms: float,
        tts_time_ms: float,
        total_time_ms: float,
        success: bool = True,
        error_message: Optional[str] = None,
        cache_hit: bool = False,
        streaming: bool = False,
        text_length: int = 0
    ) -> None:
        """Record metrics for a request.

        Args:
            session_id: Session identifier
            stt_time_ms: Speech-to-text processing time
            ai_time_ms: AI generation time
            tts_time_ms: Text-to-speech time
            total_time_ms: Total processing time
            success: Whether request succeeded
            error_message: Error message if failed
            cache_hit: Whether response came from cache
            streaming: Whether response was streamed
            text_length: Length of response text
        """
        # Create request metrics
        metrics = RequestMetrics(
            timestamp=time.time(),
            session_id=session_id,
            stt_time_ms=stt_time_ms,
            ai_time_ms=ai_time_ms,
            tts_time_ms=tts_time_ms,
            total_time_ms=total_time_ms,
            success=success,
            error_message=error_message,
            cache_hit=cache_hit,
            streaming=streaming,
            text_length=text_length
        )

        # Add to history
        self.request_history.append(metrics)

        # Update counters
        self.total_requests += 1
        if not success:
            self.total_errors += 1
        if cache_hit:
            self.total_cache_hits += 1
        if streaming:
            self.total_streaming_requests += 1

        # Update timing stats
        self.total_stt_time_ms += stt_time_ms
        self.total_ai_time_ms += ai_time_ms
        self.total_tts_time_ms += tts_time_ms
        self.total_processing_time_ms += total_time_ms

        # Update session metrics
        if session_id in self.active_sessions:
            session = self.active_sessions[session_id]
            session.request_count += 1
            session.total_processing_time_ms += total_time_ms
            if not success:
                session.errors += 1
            if cache_hit:
                session.cache_hits += 1

        logger.debug(f"Recorded metrics for request in session {session_id}")

    def start_session(self, session_id: str) -> None:
        """Start tracking a new session.

        Args:
            session_id: Session identifier
        """
        session = SessionMetrics(
            session_id=session_id,
            start_time=time.time()
        )
        self.active_sessions[session_id] = session
        logger.info(f"Started tracking session: {session_id}")

    def end_session(self, session_id: str) -> None:
        """End tracking a session.

        Args:
            session_id: Session identifier
        """
        if session_id in self.active_sessions:
            session = self.active_sessions[session_id]
            session.end_time = time.time()

            # Move to history
            self.session_history.append(session)
            del self.active_sessions[session_id]

            logger.info(f"Ended tracking session: {session_id}")

    def get_recent_requests(self, limit: int = 10) -> List[Dict]:
        """Get recent request metrics.

        Args:
            limit: Maximum number of requests to return

        Returns:
            List of request metric dictionaries
        """
        recent = list(self.request_history)[-limit:]
        return [
            {
                "timestamp": r.timestamp,
                "session_id": r.session_id,
                "stt_time_ms": r.stt_time_ms,
                "ai_time_ms": r.ai_time_ms,
                "tts_time_ms": r.tts_time_ms,
                "total_time_ms": r.total_time_ms,
                "success": r.success,
                "error_message": r.error_message,
                "cache_hit": r.cache_hit,
                "streaming": r.streaming,
                "text_length": r.text_length
            }
            for r in recent
        ]

    def get_aggregate_stats(self, window_seconds: Optional[int] = None) -> Dict:
        """Get aggregated statistics.

        Args:
            window_seconds: Time window in seconds (None for all-time)

        Returns:
            Aggregated statistics dictionary
        """
        if window_seconds:
            # Filter to time window
            cutoff = time.time() - window_seconds
            requests = [r for r in self.request_history if r.timestamp >= cutoff]
        else:
            requests = list(self.request_history)

        if not requests:
            return {
                "request_count": 0,
                "success_rate": 0.0,
                "cache_hit_rate": 0.0,
                "streaming_rate": 0.0,
                "avg_stt_time_ms": 0.0,
                "avg_ai_time_ms": 0.0,
                "avg_tts_time_ms": 0.0,
                "avg_total_time_ms": 0.0,
                "p50_total_time_ms": 0.0,
                "p95_total_time_ms": 0.0,
                "p99_total_time_ms": 0.0
            }

        # Calculate stats
        total_count = len(requests)
        success_count = sum(1 for r in requests if r.success)
        cache_hits = sum(1 for r in requests if r.cache_hit)
        streaming_count = sum(1 for r in requests if r.streaming)

        avg_stt = sum(r.stt_time_ms for r in requests) / total_count
        avg_ai = sum(r.ai_time_ms for r in requests) / total_count
        avg_tts = sum(r.tts_time_ms for r in requests) / total_count
        avg_total = sum(r.total_time_ms for r in requests) / total_count

        # Calculate percentiles
        total_times = sorted(r.total_time_ms for r in requests)
        p50_idx = int(len(total_times) * 0.50)
        p95_idx = int(len(total_times) * 0.95)
        p99_idx = int(len(total_times) * 0.99)

        return {
            "request_count": total_count,
            "success_rate": success_count / total_count if total_count > 0 else 0.0,
            "cache_hit_rate": cache_hits / total_count if total_count > 0 else 0.0,
            "streaming_rate": streaming_count / total_count if total_count > 0 else 0.0,
            "avg_stt_time_ms": avg_stt,
            "avg_ai_time_ms": avg_ai,
            "avg_tts_time_ms": avg_tts,
            "avg_total_time_ms": avg_total,
            "p50_total_time_ms": total_times[p50_idx] if p50_idx < len(total_times) else 0.0,
            "p95_total_time_ms": total_times[p95_idx] if p95_idx < len(total_times) else 0.0,
            "p99_total_time_ms": total_times[p99_idx] if p99_idx < len(total_times) else 0.0
        }

    def get_dashboard_metrics(self) -> Dict:
        """Get comprehensive metrics for dashboard.

        Returns:
            Dashboard metrics dictionary
        """
        uptime = time.time() - self.start_time

        # All-time stats
        all_time_stats = self.get_aggregate_stats()

        # Last hour stats
        last_hour_stats = self.get_aggregate_stats(window_seconds=3600)

        # Last minute stats
        last_minute_stats = self.get_aggregate_stats(window_seconds=60)

        # Session stats
        active_session_count = len(self.active_sessions)
        avg_requests_per_session = (
            sum(s.request_count for s in self.active_sessions.values()) / active_session_count
            if active_session_count > 0 else 0.0
        )

        return {
            "system": {
                "uptime_seconds": uptime,
                "uptime_formatted": self._format_uptime(uptime)
            },
            "totals": {
                "total_requests": self.total_requests,
                "total_errors": self.total_errors,
                "total_cache_hits": self.total_cache_hits,
                "total_streaming_requests": self.total_streaming_requests,
                "error_rate": self.total_errors / self.total_requests if self.total_requests > 0 else 0.0,
                "cache_hit_rate": self.total_cache_hits / self.total_requests if self.total_requests > 0 else 0.0
            },
            "sessions": {
                "active_count": active_session_count,
                "total_completed": len(self.session_history),
                "avg_requests_per_session": avg_requests_per_session,
                "active_sessions": [
                    {
                        "session_id": s.session_id,
                        "request_count": s.request_count,
                        "duration_seconds": time.time() - s.start_time,
                        "errors": s.errors,
                        "cache_hits": s.cache_hits
                    }
                    for s in self.active_sessions.values()
                ]
            },
            "performance": {
                "all_time": all_time_stats,
                "last_hour": last_hour_stats,
                "last_minute": last_minute_stats
            },
            "recent_requests": self.get_recent_requests(limit=20)
        }

    def _format_uptime(self, seconds: float) -> str:
        """Format uptime in human-readable form.

        Args:
            seconds: Uptime in seconds

        Returns:
            Formatted uptime string
        """
        days = int(seconds // 86400)
        hours = int((seconds % 86400) // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)

        if days > 0:
            return f"{days}d {hours}h {minutes}m"
        elif hours > 0:
            return f"{hours}h {minutes}m {secs}s"
        elif minutes > 0:
            return f"{minutes}m {secs}s"
        else:
            return f"{secs}s"

    def reset(self) -> None:
        """Reset all metrics."""
        self.request_history.clear()
        self.active_sessions.clear()
        self.session_history.clear()
        self.total_requests = 0
        self.total_errors = 0
        self.total_cache_hits = 0
        self.total_streaming_requests = 0
        self.total_stt_time_ms = 0.0
        self.total_ai_time_ms = 0.0
        self.total_tts_time_ms = 0.0
        self.total_processing_time_ms = 0.0
        self.start_time = time.time()
        logger.info("Metrics reset")
