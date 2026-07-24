"""
TTS Service - Text-to-Speech processing with multiple provider support
Handles voice synthesis with natural speech parameters
"""

import asyncio
import json
import base64
import logging
from typing import Optional, Dict, Any
import httpx

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class TTSService:
    """
    Text-to-Speech service with provider abstraction and voice customization
    """
    
    def __init__(self, provider: str = "elevenlabs"):
        """
        Initialize TTS Service
        
        Args:
            provider: TTS provider name
        """
        self.provider = provider
        self._client = None
        self._initialized = False
        self._audio_cache = {}
        self._max_cache_size = 100
        
        # Provider configurations
        self.providers = {
            "elevenlabs": self._elevenlabs_synthesize,
            "azure": self._azure_synthesize,
            "google": self._google_synthesize,
        }
        
        # Voice profiles
        self.voice_profiles = {
            "default": {
                "voice_id": settings.tts_voice_id,
                "stability": settings.tts_stability,
                "similarity_boost": settings.tts_similarity_boost,
                "style": settings.tts_style,
                "speed": settings.tts_speed,
            },
            "professional": {
                "voice_id": "21m00Tcm4TlvDq8ikWAM",
                "stability": 0.8,
                "similarity_boost": 0.8,
                "style": 0.1,
                "speed": 0.9,
            },
            "empathetic": {
                "voice_id": "21m00Tcm4TlvDq8ikWAM",
                "stability": 0.3,
                "similarity_boost": 0.9,
                "style": 0.5,
                "speed": 1.0,
            },
        }
        
        logger.info(f"TTS Service initialized: provider={provider}")
    
    async def initialize(self) -> None:
        """Initialize HTTP client"""
        if not self._client:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                limits=httpx.Limits(max_keepalive_connections=10, max_connections=50)
            )
            self._initialized = True
            logger.info("TTS HTTP client initialized")
    
    async def synthesize(
        self,
        text: str,
        voice_profile: str = "default",
        cache: bool = True
    ) -> Optional[bytes]:
        """
        Synthesize text to audio
        
        Args:
            text: Text to synthesize
            voice_profile: Voice profile name
            cache: Whether to cache the result
        
        Returns:
            Audio bytes or None
        """
        if not self._initialized:
            await self.initialize()
        
        if not text or len(text.strip()) == 0:
            return None
        
        # Check cache
        if cache:
            cache_key = f"{self.provider}_{voice_profile}_{text}"
            if cache_key in self._audio_cache:
                logger.debug(f"TTS cache hit: {text[:30]}...")
                return self._audio_cache[cache_key]
        
        # Synthesize
        if self.provider not in self.providers:
            logger.error(f"Unknown TTS provider: {self.provider}")
            return None
        
        try:
            audio = await self.providers[self.provider](text, voice_profile)
            
            # Cache
            if cache and audio and len(self._audio_cache) < self._max_cache_size:
                cache_key = f"{self.provider}_{voice_profile}_{text}"
                self._audio_cache[cache_key] = audio
                logger.debug(f"TTS cached: {text[:30]}...")
            
            return audio
            
        except Exception as e:
            logger.error(f"TTS synthesis error: {e}")
            return None
    
    async def _elevenlabs_synthesize(
        self,
        text: str,
        voice_profile: str
    ) -> Optional[bytes]:
        """Synthesize using ElevenLabs API"""
        if not settings.elevenlabs_api_key:
            logger.warning("ElevenLabs API key not configured")
            return None
        
        # Get voice settings
        voice_config = self.voice_profiles.get(voice_profile, self.voice_profiles["default"])
        voice_id = voice_config.get("voice_id", settings.tts_voice_id)
        
        try:
            response = await self._client.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
                headers={
                    "xi-api-key": settings.elevenlabs_api_key,
                    "Content-Type": "application/json"
                },
                json={
                    "text": text,
                    "model_id": settings.tts_model,
                    "voice_settings": {
                        "stability": voice_config.get("stability", settings.tts_stability),
                        "similarity_boost": voice_config.get("similarity_boost", settings.tts_similarity_boost),
                        "style": voice_config.get("style", settings.tts_style),
                        "use_speaker_boost": True
                    }
                }
            )
            response.raise_for_status()
            
            # Validate audio data
            audio = response.content
            if len(audio) < 100:  # Too small to be valid audio
                logger.warning(f"TTS audio too small: {len(audio)} bytes")
                return None
            
            return audio
            
        except httpx.HTTPStatusError as e:
            logger.error(f"ElevenLabs API error: {e.response.status_code}")
            if e.response.status_code == 401:
                logger.error("Invalid ElevenLabs API key")
            elif e.response.status_code == 429:
                logger.error("ElevenLabs rate limit exceeded")
            return None
        except Exception as e:
            logger.error(f"ElevenLabs synthesis error: {e}")
            return None
    
    async def _azure_synthesize(
        self,
        text: str,
        voice_profile: str
    ) -> Optional[bytes]:
        """Synthesize using Azure Speech Services"""
        # Implement Azure TTS
        logger.warning("Azure TTS not yet implemented")
        return None
    
    async def _google_synthesize(
        self,
        text: str,
        voice_profile: str
    ) -> Optional[bytes]:
        """Synthesize using Google Cloud Text-to-Speech"""
        # Implement Google TTS
        logger.warning("Google TTS not yet implemented")
        return None
    
    async def cleanup(self) -> None:
        """Clean up resources"""
        if self._client:
            await self._client.aclose()
            self._client = None
            self._initialized = False
            self._audio_cache.clear()
            logger.info("TTS Service cleaned up")