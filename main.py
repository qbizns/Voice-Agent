"""Main FastAPI application entry point."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.api import routes
from app.api import live_routes
from app.services.stt_service import STTService
from app.services.tts_service import TTSService
from app.services.streaming_tts_service import StreamingTTSService
from app.services.knowledge_base import KnowledgeBase
from app.services.ai_agent import AIAgent
from app.services.lipsync_service import LipSyncService
from app.services.vad_service import VADService
from app.services.context_service import ContextService
from app.services.cache_service import ResponseCache


# Initialize services
stt_service: STTService | None = None
tts_service: TTSService | None = None
streaming_tts_service: StreamingTTSService | None = None
knowledge_base: KnowledgeBase | None = None
ai_agent: AIAgent | None = None
lipsync_service: LipSyncService | None = None
vad_service: VADService | None = None
context_service: ContextService | None = None
cache_service: ResponseCache | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global stt_service, tts_service, streaming_tts_service, knowledge_base, ai_agent, lipsync_service, vad_service, context_service, cache_service

    # Setup logging
    setup_logging()
    settings = get_settings()

    logger.info(f"Starting {settings.app_name} v{settings.app_version}")

    # Initialize services
    try:
        logger.info("Initializing services...")

        # Initialize STT
        logger.info("Initializing Speech-to-Text service...")
        stt_service = STTService()

        # Initialize TTS
        logger.info("Initializing Text-to-Speech service...")
        tts_service = TTSService()

        # Initialize Streaming TTS
        logger.info("Initializing Streaming TTS service...")
        streaming_tts_service = StreamingTTSService()
        if streaming_tts_service.enabled:
            logger.info("Streaming TTS enabled for sentence-by-sentence generation")
        else:
            logger.warning("Streaming TTS disabled (edge-tts not available)")

        # Initialize Knowledge Base
        logger.info("Initializing Knowledge Base...")
        knowledge_base = KnowledgeBase()

        # Load documents from knowledge base directory if it exists
        kb_path = Path(settings.knowledge_base_path)
        if kb_path.exists():
            logger.info(f"Loading documents from {kb_path}")
            knowledge_base.load_documents_from_directory(kb_path)
        else:
            logger.warning(f"Knowledge base directory not found: {kb_path}")
            kb_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created knowledge base directory: {kb_path}")

        # Initialize AI Agent
        logger.info("Initializing AI Agent...")
        ai_agent = AIAgent(knowledge_base=knowledge_base)

        # Initialize Lip-Sync Service
        logger.info("Initializing Lip-Sync service...")
        lipsync_service = LipSyncService()
        if lipsync_service.enabled:
            logger.info("Lip-sync enabled with Rhubarb")
        else:
            logger.warning("Lip-sync disabled (Rhubarb not found)")

        # Initialize VAD Service
        logger.info("Initializing Voice Activity Detection service...")
        vad_service = VADService(
            threshold=0.5,
            sampling_rate=16000,
            min_silence_duration_ms=800
        )
        if vad_service.enabled:
            logger.info("VAD enabled with Silero")
        else:
            logger.warning("VAD disabled (Silero not available)")

        # Initialize Context Service
        logger.info("Initializing Conversation Context service...")
        context_service = ContextService(
            max_history_per_session=10,
            session_timeout_seconds=1800  # 30 minutes
        )
        logger.info("Context service enabled for multi-turn conversations")

        # Initialize Response Cache Service
        logger.info("Initializing Response Cache service...")
        cache_service = ResponseCache(
            max_entries=1000,
            default_ttl_seconds=3600,  # 1 hour
            similarity_threshold=0.85
        )
        logger.info("Response cache enabled with semantic similarity matching")

        # Set services in routes
        routes.set_services(stt_service, tts_service, ai_agent, knowledge_base, lipsync_service)
        live_routes.set_services(stt_service, tts_service, ai_agent, knowledge_base, vad_service, context_service, cache_service, streaming_tts_service)

        logger.info("All services initialized successfully!")
        logger.info(f"Server ready at http://{settings.host}:{settings.port}")
        logger.info(f"WebSocket endpoint: ws://{settings.host}:{settings.port}/ws/conversation")
        logger.info(f"Live demo page: http://{settings.host}:{settings.port}/live")

    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
        raise

    yield

    # Cleanup
    logger.info("Shutting down services...")
    if ai_agent:
        await ai_agent.close()
    logger.info("Shutdown complete")


# Create FastAPI app
settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Ultra-fast Arabic voice agent with real-time conversation support",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
app.include_router(routes.router, prefix="/api/v1", tags=["voice-agent"])
app.include_router(live_routes.router, tags=["live-demo"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "running",
        "docs": "/docs",
        "websocket": "/api/v1/ws/conversation"
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )
