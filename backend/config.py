"""
Configuration Management for Healthcare Voice AI Assistant
Centralized, type-safe configuration with environment variable validation
"""

import os
from typing import List, Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field, field_validator, ConfigDict
from pydantic_settings import BaseSettings
from functools import lru_cache


class Provider(str, Enum):
    """Available service providers"""
    GROQ = "groq"
    GEMINI = "gemini"
    OPENAI = "openai"
    DEEPGRAM = "deepgram"
    ELEVENLABS = "elevenlabs"
    AZURE = "azure"
    BROWSER = "browser"


class LogLevel(str, Enum):
    """Logging levels"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class Settings(BaseSettings):
    """
    Application settings with validation and type safety.
    All settings are loaded from environment variables.
    """
    
    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # ============ LLM Settings ============
    llm_provider: Provider = Provider.GROQ
    groq_api_key: str = Field(..., min_length=10)
    gemini_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    azure_openai_endpoint: Optional[str] = None
    azure_openai_key: Optional[str] = None
    
    llm_model: str = "llama-3.1-8b-instant"
    llm_temperature: float = Field(0.7, ge=0.0, le=2.0)
    llm_max_tokens: int = Field(150, ge=1, le=4096)
    llm_timeout: int = Field(30, ge=1, le=120)
    llm_retry_attempts: int = Field(3, ge=1, le=5)
    llm_fallback_enabled: bool = True
    
    # ============ STT Settings ============
    stt_provider: Provider = Provider.DEEPGRAM
    deepgram_api_key: str = Field(..., min_length=10)
    stt_model: str = "nova-2"
    stt_language: str = "en"
    stt_smart_format: bool = True
    stt_punctuate: bool = True
    stt_diarize: bool = False
    stt_streaming: bool = True
    stt_interim_results: bool = True
    
    # ============ TTS Settings ============
    tts_provider: Provider = Provider.ELEVENLABS
    elevenlabs_api_key: str = Field(..., min_length=10)
    tts_voice_id: str = "21m00Tcm4TlvDq8ikWAM"
    tts_model: str = "eleven_monolingual_v1"
    tts_stability: float = Field(0.5, ge=0.0, le=1.0)
    tts_similarity_boost: float = Field(0.75, ge=0.0, le=1.0)
    tts_style: float = Field(0.0, ge=0.0, le=1.0)
    tts_speed: float = Field(1.0, ge=0.5, le=2.0)
    
    # ============ Session Settings ============
    session_timeout: int = Field(300, ge=10, le=3600)
    max_concurrent_sessions: int = Field(1000, ge=1, le=10000)
    max_session_history: int = Field(50, ge=1, le=500)
    
    # ============ WebSocket Settings ============
    max_websocket_connections: int = Field(1000, ge=1, le=10000)
    websocket_timeout: int = Field(30, ge=5, le=120)
    websocket_heartbeat_interval: int = Field(15, ge=5, le=60)
    websocket_max_message_size: int = Field(10_000_000, ge=1024, le=50_000_000)
    
    # ============ CORS Settings ============
    allowed_origins: List[str] = Field(
        default=["http://localhost:3000", "https://*.vercel.app"],
        description="Allowed origins for CORS"
    )
    allowed_methods: List[str] = ["GET", "POST", "OPTIONS"]
    allowed_headers: List[str] = ["*"]
    
    # ============ System Settings ============
    log_level: LogLevel = LogLevel.INFO
    environment: str = Field("development", pattern="^(development|staging|production)$")
    debug: bool = Field(False)
    enable_metrics: bool = Field(True)
    enable_tracing: bool = Field(False)
    
    # ============ Security Settings ============
    rate_limit_enabled: bool = True
    rate_limit_requests: int = Field(100, ge=1, le=10000)
    rate_limit_period: int = Field(60, ge=1, le=3600)
    max_audio_duration: int = Field(60, ge=1, le=300)
    
    # ============ Prompts ============
    system_prompt: str = """You are a compassionate healthcare AI assistant. Your role is to:
1. Be empathetic and understanding in all responses
2. Provide concise responses (1-2 sentences when possible)
3. Ask clarifying questions when needed
4. Never provide specific medical advice or diagnoses
5. Always recommend consulting a healthcare professional when appropriate
6. Use clear, accessible language without markdown or special characters
7. Maintain a warm, professional tone

Remember: You are not a doctor. Your purpose is to support and guide users toward proper healthcare resources."""
    
    # ============ Validators ============
    @field_validator("llm_provider", mode="before")
    @classmethod
    def validate_llm_provider(cls, v):
        """Validate LLM provider has required API keys"""
        if v == Provider.GROQ and not os.getenv("GROQ_API_KEY"):
            raise ValueError("GROQ_API_KEY is required when using Groq provider")
        if v == Provider.GEMINI and not os.getenv("GEMINI_API_KEY"):
            raise ValueError("GEMINI_API_KEY is required when using Gemini provider")
        if v == Provider.OPENAI and not os.getenv("OPENAI_API_KEY"):
            raise ValueError("OPENAI_API_KEY is required when using OpenAI provider")
        return v
    
    @field_validator("stt_provider", mode="before")
    @classmethod
    def validate_stt_provider(cls, v):
        """Validate STT provider has required API keys"""
        if v == Provider.DEEPGRAM and not os.getenv("DEEPGRAM_API_KEY"):
            raise ValueError("DEEPGRAM_API_KEY is required when using Deepgram provider")
        return v
    
    @field_validator("tts_provider", mode="before")
    @classmethod
    def validate_tts_provider(cls, v):
        """Validate TTS provider has required API keys"""
        if v == Provider.ELEVENLABS and not os.getenv("ELEVENLABS_API_KEY"):
            raise ValueError("ELEVENLABS_API_KEY is required when using ElevenLabs provider")
        return v


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.
    Returns singleton Settings object.
    """
    return Settings()


class Config:
    """Configuration utilities"""
    
    @staticmethod
    def get_sensitive_keys() -> List[str]:
        """Get list of sensitive keys that should be masked in logs"""
        return [
            "api_key", "secret", "password", "token", 
            "key", "auth", "credential", "private"
        ]
    
    @staticmethod
    def mask_sensitive_data(data: Dict[str, Any]) -> Dict[str, Any]:
        """Mask sensitive data for logging"""
        masked = {}
        for key, value in data.items():
            if any(sensitive in key.lower() for sensitive in Config.get_sensitive_keys()):
                masked[key] = "***MASKED***"
            else:
                masked[key] = value
        return masked