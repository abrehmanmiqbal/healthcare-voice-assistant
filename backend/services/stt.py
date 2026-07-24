"""
STT Service - Speech-to-Text processing with multiple provider support
Handles both streaming and full audio transcription
"""

import asyncio
import json
import base64
import logging
from typing import Optional, Dict, Any
import httpx
import wave
import io
import os

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class STTService:
    """
    Speech-to-Text service with provider abstraction and streaming support
    """
    
    def __init__(self, provider: str = "deepgram"):
        """
        Initialize STT Service
        
        Args:
            provider: STT provider name
        """
        self.provider = provider
        self._client = None
        self._initialized = False
        self._debug_dir = "audio_debug"
        # OFF by default: writing files into this backend directory while
        # uvicorn --reload is watching it triggers a full server reload
        # mid-conversation, which kills the websocket before a response can
        # be sent. Set STT_SAVE_DEBUG_AUDIO=true only if you need to inspect
        # raw audio, and run uvicorn without --reload (or exclude this dir)
        # while doing so.
        self._save_debug = os.getenv("STT_SAVE_DEBUG_AUDIO", "false").lower() == "true"
        
        # Create debug directory only if debug saving is enabled
        if self._save_debug:
            os.makedirs(self._debug_dir, exist_ok=True)
        
        # Provider configurations
        self.providers = {
            "deepgram": self._deepgram_transcribe,
            "azure": self._azure_transcribe,
            "google": self._google_transcribe,
        }
        
        logger.info(f"STT Service initialized: provider={provider}")
    
    async def initialize(self) -> None:
        """Initialize HTTP client"""
        if not self._client:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                limits=httpx.Limits(max_keepalive_connections=10, max_connections=50)
            )
            self._initialized = True
            logger.info("STT HTTP client initialized")
    
    async def transcribe(self, audio_data: bytes) -> Optional[str]:
        """
        Transcribe audio to text
        
        Args:
            audio_data: Raw audio bytes
        
        Returns:
            Transcribed text or None
        """
        if not self._initialized:
            await self.initialize()
        
        if self.provider not in self.providers:
            logger.error(f"Unknown STT provider: {self.provider}")
            return None
        
        try:
            return await self.providers[self.provider](audio_data)
        except Exception as e:
            logger.error(f"STT transcription error: {e}")
            return None
    
    async def transcribe_stream(self, audio_chunk: bytes) -> Optional[str]:
        """
        Stream audio for real-time transcription
        
        Args:
            audio_chunk: Audio chunk bytes
        
        Returns:
            Interim transcript or None
        """
        try:
            if len(audio_chunk) < 1000:
                return None
            return await self.transcribe(audio_chunk)
        except Exception as e:
            logger.error(f"Stream transcription error: {e}")
            return None
    
    def _save_debug_audio(self, audio_data: bytes, prefix: str = "audio") -> str:
        """Save audio for debugging (no-op unless STT_SAVE_DEBUG_AUDIO=true)"""
        if not self._save_debug:
            return ""
        try:
            import time
            filename = f"{self._debug_dir}/{prefix}_{int(time.time())}.webm"
            with open(filename, "wb") as f:
                f.write(audio_data)
            logger.info(f"💾 Saved debug audio: {filename}")
            return filename
        except Exception as e:
            logger.error(f"Failed to save debug audio: {e}")
            return ""
    
    async def _deepgram_transcribe(self, audio_data: bytes) -> Optional[str]:
        """Transcribe using Deepgram API"""
        if not settings.deepgram_api_key:
            logger.warning("Deepgram API key not configured")
            return None
        
        try:
            # Save audio for debugging
            self._save_debug_audio(audio_data, "input")
            
            audio_size = len(audio_data)
            logger.info(f"📊 Audio size: {audio_size} bytes")
            
            if audio_size < 500:
                logger.warning("⚠️ Audio too small, skipping transcription")
                return None
            
            # Try with raw audio first (as WebM)
            # Deepgram accepts WebM directly
            response = await self._client.post(
                "https://api.deepgram.com/v1/listen",
                headers={
                    "Authorization": f"Token {settings.deepgram_api_key}",
                    "Content-Type": "audio/webm",
                },
                params={
                    "model": "nova-2",
                    "language": "en",
                    "smart_format": "true",
                    "punctuate": "true",
                    "diarize": "false",
                },
                content=audio_data
            )
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"📥 Deepgram Response: {json.dumps(data, indent=2)[:500]}")
                
                transcript = (
                    data.get("results", {})
                    .get("channels", [{}])[0]
                    .get("alternatives", [{}])[0]
                    .get("transcript", "")
                )
                
                transcript = transcript.strip()
                
                if transcript:
                    logger.info(f"✅ Deepgram transcription: '{transcript}'")
                    return transcript
                else:
                    logger.warning("⚠️ Deepgram returned empty transcript")
                    
                    # Try with WAV format as fallback
                    logger.info("🔄 Trying with WAV format...")
                    
                    # Convert to WAV
                    wav_audio = self._create_wav_from_pcm(audio_data)
                    self._save_debug_audio(wav_audio, "converted_wav")
                    
                    response2 = await self._client.post(
                        "https://api.deepgram.com/v1/listen",
                        headers={
                            "Authorization": f"Token {settings.deepgram_api_key}",
                            "Content-Type": "audio/wav",
                        },
                        params={
                            "model": "nova-2",
                            "language": "en",
                            "smart_format": "true",
                            "punctuate": "true",
                        },
                        content=wav_audio
                    )
                    
                    if response2.status_code == 200:
                        data2 = response2.json()
                        transcript2 = (
                            data2.get("results", {})
                            .get("channels", [{}])[0]
                            .get("alternatives", [{}])[0]
                            .get("transcript", "")
                        )
                        transcript2 = transcript2.strip()
                        if transcript2:
                            logger.info(f"✅ WAV format worked: '{transcript2}'")
                            return transcript2
                    
                    return None
            else:
                error_text = response.text[:300]
                logger.error(f"❌ Deepgram API error {response.status_code}: {error_text}")
                
                # If WebM fails, try WAV
                logger.info("🔄 WebM failed, trying WAV format...")
                wav_audio = self._create_wav_from_pcm(audio_data)
                
                response2 = await self._client.post(
                    "https://api.deepgram.com/v1/listen",
                    headers={
                        "Authorization": f"Token {settings.deepgram_api_key}",
                        "Content-Type": "audio/wav",
                    },
                    params={
                        "model": "nova-2",
                        "language": "en",
                        "smart_format": "true",
                        "punctuate": "true",
                    },
                    content=wav_audio
                )
                
                if response2.status_code == 200:
                    data2 = response2.json()
                    transcript2 = (
                        data2.get("results", {})
                        .get("channels", [{}])[0]
                        .get("alternatives", [{}])[0]
                        .get("transcript", "")
                    )
                    transcript2 = transcript2.strip()
                    if transcript2:
                        logger.info(f"✅ WAV format worked: '{transcript2}'")
                        return transcript2
                
                return None
                
        except httpx.TimeoutException:
            logger.error("❌ Deepgram timeout - API took too long")
            return None
        except Exception as e:
            logger.error(f"❌ Deepgram transcription error: {e}")
            return None
    
    def _create_wav_from_pcm(self, pcm_data: bytes, sample_rate: int = 16000) -> bytes:
        """Create WAV file from PCM data"""
        try:
            # If data looks like WebM, try to extract PCM
            if pcm_data[:4] == b'\x1a\x45\xdf\xa3':
                # WebM format - return as is, Deepgram can handle it
                return pcm_data
            
            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, 'wb') as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(pcm_data)
            
            return wav_buffer.getvalue()
        except Exception as e:
            logger.error(f"WAV creation error: {e}")
            return pcm_data
    
    async def _azure_transcribe(self, audio_data: bytes) -> Optional[str]:
        """Transcribe using Azure Speech Services"""
        logger.warning("Azure STT not yet implemented")
        return None
    
    async def _google_transcribe(self, audio_data: bytes) -> Optional[str]:
        """Transcribe using Google Cloud Speech-to-Text"""
        logger.warning("Google STT not yet implemented")
        return None
    
    async def cleanup(self) -> None:
        """Clean up resources"""
        if self._client:
            await self._client.aclose()
            self._client = None
            self._initialized = False
            logger.info("STT Service cleaned up")