"""
Voice Pipeline - Orchestrates the complete voice processing flow
Handles streaming audio, STT, LLM, and TTS with error recovery
"""

import asyncio
import base64
import json
import time
import logging
from typing import Dict, Any, Optional, List, Tuple
from fastapi import WebSocket
from collections import defaultdict

from .session_manager import SessionManager
from .llm import LLMService
from .stt import STTService
from .tts import TTSService

logger = logging.getLogger(__name__)


class VoicePipeline:
    """
    Orchestrates the complete voice processing pipeline:
    Audio → STT → LLM → TTS → Audio Response
    """
    
    def __init__(
        self,
        session_manager: SessionManager,
        stt_provider: str = "deepgram",
        llm_provider: str = "groq",
        tts_provider: str = "elevenlabs"
    ):
        """
        Initialize Voice Pipeline
        
        Args:
            session_manager: SessionManager instance
            stt_provider: STT provider name
            llm_provider: LLM provider name
            tts_provider: TTS provider name
        """
        self.session_manager = session_manager
        self.stt_provider = stt_provider
        self.llm_provider = llm_provider
        self.tts_provider = tts_provider
        
        # Services
        self.stt: Optional[STTService] = None
        self.llm: Optional[LLMService] = None
        self.tts: Optional[TTSService] = None
        
        # Audio buffers per session
        self.audio_buffers: Dict[str, List[bytes]] = defaultdict(list)
        self.is_processing: Dict[str, bool] = defaultdict(bool)
        self.last_transcript: Dict[str, str] = {}
        
        # Metrics
        self.metrics = {
            "total_requests": 0,
            "avg_stt_time": 0,
            "avg_llm_time": 0,
            "avg_tts_time": 0,
        }
        
        self._lock = asyncio.Lock()
        self._initialized = False
        
        logger.info(f"VoicePipeline initialized: STT={stt_provider}, LLM={llm_provider}, TTS={tts_provider}")
    
    async def initialize(self) -> None:
        """Initialize all service providers"""
        if self._initialized:
            return
        
        try:
            # Initialize STT
            self.stt = STTService(provider=self.stt_provider)
            await self.stt.initialize()
            
            # Initialize LLM
            self.llm = LLMService(provider=self.llm_provider)
            await self.llm.initialize()
            
            # Initialize TTS
            self.tts = TTSService(provider=self.tts_provider)
            await self.tts.initialize()
            
            self._initialized = True
            logger.info("VoicePipeline fully initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize VoicePipeline: {e}")
            raise
    
    async def process_message(
        self,
        session_id: str,
        data: Dict[str, Any],
        websocket: WebSocket
    ) -> None:
        """
        Process incoming WebSocket message
        
        Args:
            session_id: Session ID
            data: Message data
            websocket: WebSocket connection
        """
        if not self._initialized:
            await self.initialize()
        
        msg_type = data.get("type")
        
        try:
            if msg_type == "start":
                await self._handle_start(session_id, websocket)
                
            elif msg_type == "audio":
                await self._handle_audio(session_id, data, websocket)
                
            elif msg_type == "stop":
                await self._handle_stop(session_id, websocket)
                
            else:
                logger.warning(f"Unknown message type: {msg_type}")
                
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            await self._send_error(websocket, "Processing error")
    
    async def _handle_start(self, session_id: str, websocket: WebSocket) -> None:
        """Handle start of audio stream"""
        self.audio_buffers[session_id] = []
        self.is_processing[session_id] = False
        self.last_transcript[session_id] = ""
        
        await self._send_status(websocket, "listening")
        logger.info(f"🎤 Started listening: {session_id[:8]}")
    
    async def _handle_audio(
        self,
        session_id: str,
        data: Dict[str, Any],
        websocket: WebSocket
    ) -> None:
        """Handle incoming audio chunk"""
        audio_data = data.get("data", "")
        
        if not audio_data:
            return
        
        try:
            # Decode base64 audio
            audio_bytes = base64.b64decode(audio_data)
            self.audio_buffers[session_id].append(audio_bytes)
            
        except Exception as e:
            logger.error(f"Audio processing error: {e}")
    
    async def _handle_stop(self, session_id: str, websocket: WebSocket) -> None:
        """Handle end of audio stream"""
        if self.is_processing[session_id]:
            return
        
        try:
            self.is_processing[session_id] = True
            
            # Get complete audio
            audio_chunks = self.audio_buffers.get(session_id, [])
            if not audio_chunks:
                await self._send_status(websocket, "idle")
                self.is_processing[session_id] = False
                return
            
            # Combine chunks
            full_audio = b''.join(audio_chunks)
            
            # Send thinking status
            await self._send_status(websocket, "thinking")
            
            # STT Transcription
            start_time = time.time()
            transcript = await self.stt.transcribe(full_audio)
            stt_time = time.time() - start_time
            
            if transcript:
                # Update metrics
                self.metrics["total_requests"] += 1
                self.metrics["avg_stt_time"] = (
                    (self.metrics["avg_stt_time"] * (self.metrics["total_requests"] - 1) + stt_time)
                    / self.metrics["total_requests"]
                )
                
                # Send final transcript
                await websocket.send_json({
                    "type": "transcript",
                    "text": transcript,
                    "is_final": True
                })
                
                # Add to session history
                self.session_manager.add_message(session_id, "user", transcript)
                
                # Get conversation history
                history = self.session_manager.get_recent_messages(session_id, limit=10)
                
                # LLM Processing
                await self._send_status(websocket, "thinking")
                
                start_time = time.time()
                response_text = await self.llm.generate_response(
                    user_message=transcript,
                    conversation_history=history,
                    session_id=session_id
                )
                llm_time = time.time() - start_time
                
                # Update metrics
                self.metrics["avg_llm_time"] = (
                    (self.metrics["avg_llm_time"] * (self.metrics["total_requests"] - 1) + llm_time)
                    / self.metrics["total_requests"]
                )
                
                # Store response
                self.session_manager.add_message(session_id, "assistant", response_text)
                
                # Send response
                await websocket.send_json({
                    "type": "response",
                    "text": response_text
                })
                
                # TTS Generation
                await self._send_status(websocket, "speaking")
                
                start_time = time.time()
                audio_response = await self.tts.synthesize(response_text)
                tts_time = time.time() - start_time
                
                # Update metrics
                self.metrics["avg_tts_time"] = (
                    (self.metrics["avg_tts_time"] * (self.metrics["total_requests"] - 1) + tts_time)
                    / self.metrics["total_requests"]
                )
                
                if audio_response:
                    # Send TTS audio
                    audio_b64 = base64.b64encode(audio_response).decode('utf-8')
                    await websocket.send_json({
                        "type": "tts",
                        "audio": audio_b64,
                        "format": "webm"
                    })
                
                logger.info(f"✅ Processing complete: {session_id[:8]} | STT: {stt_time:.2f}s, LLM: {llm_time:.2f}s, TTS: {tts_time:.2f}s")
                
            else:
                # No transcript - send friendly message
                await websocket.send_json({
                    "type": "response",
                    "text": "I couldn't hear you clearly. Could you please repeat that?"
                })
                logger.warning(f"No transcript for session {session_id[:8]}")
                
        except Exception as e:
            logger.error(f"Processing error: {e}", exc_info=True)
            await websocket.send_json({
                "type": "response",
                "text": "Sorry, I encountered an error. Please try again."
            })
            await self._send_error(websocket, "Processing error")
            
        finally:
            # Cleanup
            self.audio_buffers[session_id] = []
            self.is_processing[session_id] = False
            await self._send_status(websocket, "idle")
    
    async def _send_status(self, websocket: WebSocket, status: str) -> None:
        """Send status update to client"""
        try:
            await websocket.send_json({
                "type": "status",
                "status": status,
                "timestamp": time.time()
            })
        except Exception as e:
            logger.error(f"Failed to send status: {e}")
    
    async def _send_error(self, websocket: WebSocket, message: str) -> None:
        """Send error to client"""
        try:
            await websocket.send_json({
                "type": "error",
                "message": message,
                "timestamp": time.time()
            })
        except Exception:
            pass
    
    def is_ready(self) -> bool:
        """Check if pipeline is ready"""
        return (
            self._initialized and
            self.stt is not None and
            self.llm is not None and
            self.tts is not None
        )
    
    async def cleanup(self) -> None:
        """Clean up resources"""
        self.audio_buffers.clear()
        self.is_processing.clear()
        
        if self.stt:
            await self.stt.cleanup()
        if self.llm:
            await self.llm.cleanup()
        if self.tts:
            await self.tts.cleanup()
            
        logger.info("VoicePipeline cleaned up")