"""Admin routes for metrics and monitoring."""

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from loguru import logger

from app.services.metrics_service import MetricsService
from app.services.cache_service import ResponseCache
from app.services.context_service import ContextService

# Services (will be set by main app)
metrics_service: Optional[MetricsService] = None
cache_service: Optional[ResponseCache] = None
context_service: Optional[ContextService] = None


def set_services(
    metrics: Optional[MetricsService] = None,
    cache: Optional[ResponseCache] = None,
    context: Optional[ContextService] = None
) -> None:
    """Set service instances."""
    global metrics_service, cache_service, context_service
    metrics_service = metrics
    cache_service = cache
    context_service = context


router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/", response_class=HTMLResponse)
async def serve_admin_dashboard():
    """Serve the admin dashboard HTML page."""
    html_path = Path("static/admin.html")

    if not html_path.exists():
        return HTMLResponse(
            content="<h1>Error: admin.html not found</h1><p>Please ensure static/admin.html exists.</p>",
            status_code=404
        )

    with open(html_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    return HTMLResponse(content=html_content)


@router.get("/metrics")
async def get_metrics():
    """Get comprehensive metrics for dashboard."""
    if not metrics_service:
        return {"error": "Metrics service not initialized"}

    return metrics_service.get_dashboard_metrics()


@router.get("/metrics/summary")
async def get_metrics_summary():
    """Get summary metrics."""
    if not metrics_service:
        return {"error": "Metrics service not initialized"}

    return {
        "totals": metrics_service.get_dashboard_metrics()["totals"],
        "sessions": {
            "active_count": len(metrics_service.active_sessions),
            "total_completed": len(metrics_service.session_history)
        },
        "performance": metrics_service.get_aggregate_stats(window_seconds=60)
    }


@router.get("/metrics/cache")
async def get_cache_metrics():
    """Get cache statistics."""
    if not cache_service:
        return {"error": "Cache service not initialized"}

    return cache_service.get_stats()


@router.get("/metrics/context")
async def get_context_metrics():
    """Get context service statistics."""
    if not context_service:
        return {"error": "Context service not initialized"}

    return context_service.get_stats()


@router.get("/sessions")
async def get_active_sessions():
    """Get list of active sessions."""
    if not metrics_service:
        return {"error": "Metrics service not initialized"}

    return {
        "active_sessions": [
            {
                "session_id": s.session_id,
                "request_count": s.request_count,
                "total_processing_time_ms": s.total_processing_time_ms,
                "errors": s.errors,
                "cache_hits": s.cache_hits
            }
            for s in metrics_service.active_sessions.values()
        ]
    }


@router.post("/metrics/reset")
async def reset_metrics():
    """Reset all metrics (use with caution)."""
    if not metrics_service:
        return {"error": "Metrics service not initialized"}

    metrics_service.reset()
    return {"status": "success", "message": "Metrics reset"}


@router.websocket("/ws/metrics")
async def websocket_metrics_stream(websocket: WebSocket) -> None:
    """WebSocket endpoint for real-time metrics streaming.

    Sends metrics updates every second.
    """
    await websocket.accept()
    logger.info("Admin metrics WebSocket connection established")

    if not metrics_service:
        await websocket.send_json({
            "type": "error",
            "data": {"message": "Metrics service not initialized"}
        })
        await websocket.close()
        return

    try:
        import asyncio
        while True:
            # Send current metrics
            metrics = metrics_service.get_dashboard_metrics()
            await websocket.send_json({
                "type": "metrics_update",
                "data": metrics
            })

            # Wait 1 second before next update
            await asyncio.sleep(1)

    except WebSocketDisconnect:
        logger.info("Admin metrics WebSocket disconnected")
    except Exception as e:
        logger.error(f"Admin metrics WebSocket error: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "data": {"message": str(e)}
            })
        except:
            pass
