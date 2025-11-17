"""Application configuration using pydantic-settings."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # Application
    app_name: str = Field(default="Voice Agent", alias="APP_NAME")
    app_version: str = Field(default="0.1.0", alias="APP_VERSION")
    debug: bool = Field(default=False, alias="DEBUG")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # Server
    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8000, alias="PORT")

    # Audio
    sample_rate: int = Field(default=16000, alias="SAMPLE_RATE")
    channels: int = Field(default=1, alias="CHANNELS")
    chunk_size: int = Field(default=4096, alias="CHUNK_SIZE")
    audio_format: str = Field(default="int16", alias="AUDIO_FORMAT")

    # Speech-to-Text
    stt_engine: Literal["vosk", "whisper"] = Field(default="vosk", alias="STT_ENGINE")
    vosk_model_path: str = Field(
        default="models/vosk-model-ar-0.22-linto",
        alias="VOSK_MODEL_PATH"
    )
    whisper_model: str = Field(default="base", alias="WHISPER_MODEL")
    whisper_language: str = Field(default="ar", alias="WHISPER_LANGUAGE")

    # Text-to-Speech
    tts_engine: Literal["edge", "coqui"] = Field(default="edge", alias="TTS_ENGINE")
    tts_voice: str = Field(default="ar-EG-SalmaNeural", alias="TTS_VOICE")
    tts_rate: str = Field(default="+0%", alias="TTS_RATE")
    tts_volume: str = Field(default="+0%", alias="TTS_VOLUME")

    # Knowledge Base
    knowledge_base_path: str = Field(default="knowledge_base", alias="KNOWLEDGE_BASE_PATH")
    embedding_model: str = Field(
        default="sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
        alias="EMBEDDING_MODEL"
    )
    vector_db: Literal["faiss", "chromadb"] = Field(default="faiss", alias="VECTOR_DB")
    chunk_size: int = Field(default=500, alias="CHUNK_SIZE")
    chunk_overlap: int = Field(default=50, alias="CHUNK_OVERLAP")
    top_k_results: int = Field(default=3, alias="TOP_K_RESULTS")

    # AI Agent
    llm_provider: Literal["ollama", "local"] = Field(default="ollama", alias="LLM_PROVIDER")
    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")
    ollama_model: str = Field(default="llama2:7b", alias="OLLAMA_MODEL")
    temperature: float = Field(default=0.7, alias="TEMPERATURE")
    max_tokens: int = Field(default=500, alias="MAX_TOKENS")

    # System Prompt
    system_prompt: str = Field(
        default="أنت مساعد ذكي ومفيد. تجيب على الأسئلة بناءً على قاعدة المعرفة المتوفرة. "
                "كن واضحاً ومختصراً في إجاباتك.",
        alias="SYSTEM_PROMPT"
    )

    # Performance
    vad_enabled: bool = Field(default=True, alias="VAD_ENABLED")
    vad_aggressiveness: int = Field(default=3, alias="VAD_AGGRESSIVENESS")
    silence_threshold: int = Field(default=500, alias="SILENCE_THRESHOLD")


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
