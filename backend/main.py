"""
Healthcare Voice AI Assistant - Main Application Entry Point
Production-grade FastAPI application with WebSocket support
"""

import os
import json
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
import uvicorn

# Load environment variables
load_dotenv()

# Configure logging with structured format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Import services
from services.session_manager import SessionManager
from services.websocket_manager import WebSocketManager
from services.voice_pipeline import VoicePipeline
from config import Settings, get_settings

# Global service instances
settings: Settings = None
session_manager: SessionManager = None
websocket_manager: WebSocketManager = None
voice_pipeline: VoicePipeline = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager for graceful startup and shutdown.
    Handles initialization and cleanup of all services.
    """
    global settings, session_manager, websocket_manager, voice_pipeline
    
    # Startup
    logger.info("🚀 Starting Healthcare Voice AI Assistant...")
    
    try:
        # Load configuration
        settings = get_settings()
        logger.info(f"✅ Configuration loaded | Provider: {settings.llm_provider}")
        
        # Initialize services
        session_manager = SessionManager(
            timeout_seconds=settings.session_timeout,
            max_sessions=settings.max_concurrent_sessions
        )
        logger.info("✅ Session Manager initialized")
        
        websocket_manager = WebSocketManager(
            max_connections=settings.max_websocket_connections
        )
        logger.info("✅ WebSocket Manager initialized")
        
        voice_pipeline = VoicePipeline(
            session_manager=session_manager,
            stt_provider=settings.stt_provider,
            llm_provider=settings.llm_provider,
            tts_provider=settings.tts_provider
        )
        await voice_pipeline.initialize()
        logger.info("✅ Voice Pipeline initialized")
        
        # Start background tasks
        asyncio.create_task(cleanup_expired_sessions())
        
        logger.info("✅ All services initialized successfully")
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize services: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down Healthcare Voice AI Assistant...")
    
    try:
        if voice_pipeline:
            await voice_pipeline.cleanup()
        if websocket_manager:
            await websocket_manager.cleanup()
        if session_manager:
            session_manager.cleanup()
            
        logger.info("✅ Clean shutdown complete")
        
    except Exception as e:
        logger.error(f"❌ Error during shutdown: {e}")


async def cleanup_expired_sessions():
    """Background task to periodically clean up expired sessions"""
    while True:
        try:
            await asyncio.sleep(60)  # Check every minute
            if session_manager:
                expired_count = session_manager.cleanup_expired()
                if expired_count > 0:
                    logger.info(f"🧹 Cleaned up {expired_count} expired sessions")
        except Exception as e:
            logger.error(f"Error in session cleanup task: {e}")


# Create FastAPI app
app = FastAPI(
    title="Healthcare Voice AI Assistant API",
    description="Production-grade voice AI assistant for healthcare with real-time processing",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins if settings else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,
)


# ==================== HEALTH ENDPOINTS ====================

@app.get("/health", tags=["Health"])
async def health_check() -> Dict[str, Any]:
    """
    Comprehensive health check endpoint for monitoring and load balancers.
    Returns status of all services and system metrics.
    """
    try:
        service_status = {
            "session_manager": session_manager is not None,
            "websocket_manager": websocket_manager is not None,
            "voice_pipeline": voice_pipeline is not None,
            "llm": voice_pipeline.llm is not None if voice_pipeline else False,
            "stt": voice_pipeline.stt is not None if voice_pipeline else False,
            "tts": voice_pipeline.tts is not None if voice_pipeline else False,
        }
        
        all_healthy = all(service_status.values())
        
        return {
            "status": "healthy" if all_healthy else "degraded",
            "timestamp": asyncio.get_event_loop().time(),
            "services": service_status,
            "metrics": {
                "active_sessions": session_manager.get_active_count() if session_manager else 0,
                "active_connections": websocket_manager.get_connection_count() if websocket_manager else 0,
            },
            "version": app.version
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": asyncio.get_event_loop().time()
            }
        )


@app.get("/health/liveness", tags=["Health"])
async def liveness_check() -> Dict[str, str]:
    """Simple liveness probe for orchestration systems"""
    return {"status": "alive"}


@app.get("/health/readiness", tags=["Health"])
async def readiness_check() -> Dict[str, Any]:
    """Readiness probe - checks if all services are ready"""
    if voice_pipeline and voice_pipeline.is_ready():
        return {"status": "ready"}
    return JSONResponse(
        status_code=503,
        content={"status": "not_ready", "reason": "Services initializing"}
    )


# ==================== WEBSOCKET ENDPOINT ====================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    Main WebSocket endpoint for real-time voice interaction.
    Handles bidirectional audio streaming and AI responses.
    """
    session_id = None
    
    try:
        # Accept connection
        await websocket.accept()
        logger.info(f"🔌 New WebSocket connection established")
        
        # Create session
        session = session_manager.create_session()
        session_id = session.id
        
        # Register with WebSocket manager
        await websocket_manager.register(session_id, websocket)
        
        # Send session information to client
        await websocket.send_json({
            "type": "session",
            "session_id": session_id,
            "timestamp": asyncio.get_event_loop().time()
        })
        
        logger.info(f"📝 Session {session_id[:8]} created")
        
        # Message processing loop
        while True:
            try:
                # Receive message with timeout
                message = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=settings.websocket_timeout
                )
                
                # Parse and validate message
                try:
                    data = json.loads(message)
                    await validate_message(data)
                except json.JSONDecodeError:
                    await send_error(websocket, "Invalid JSON format")
                    continue
                except ValueError as e:
                    await send_error(websocket, str(e))
                    continue
                
                # Process message through voice pipeline
                await voice_pipeline.process_message(
                    session_id=session_id,
                    data=data,
                    websocket=websocket
                )
                
            except asyncio.TimeoutError:
                # Send heartbeat to keep connection alive
                await websocket.send_json({
                    "type": "heartbeat",
                    "timestamp": asyncio.get_event_loop().time()
                })
                continue
                
            except WebSocketDisconnect:
                logger.info(f"🔌 Session {session_id[:8]} disconnected")
                break
                
            except Exception as e:
                logger.error(f"Error processing message: {e}", exc_info=True)
                await send_error(websocket, "Internal server error")
                
    except WebSocketDisconnect:
        logger.info(f"🔌 Session {session_id[:8]} disconnected unexpectedly")
        
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        
    finally:
        # Cleanup
        if session_id:
            await websocket_manager.unregister(session_id)
            session_manager.end_session(session_id)
            logger.info(f"🧹 Session {session_id[:8]} cleaned up")


async def validate_message(data: Dict[str, Any]) -> None:
    """Validate incoming WebSocket messages"""
    msg_type = data.get("type")
    
    if msg_type not in ["start", "stop", "audio"]:
        raise ValueError(f"Invalid message type: {msg_type}")
    
    if msg_type == "audio" and not data.get("data"):
        raise ValueError("Audio message must contain data field")
    
    if msg_type == "audio":
        audio_data = data.get("data")
        if not isinstance(audio_data, str) or len(audio_data) > 10_000_000:  # ~10MB limit
            raise ValueError("Invalid audio data format or size")


async def send_error(websocket: WebSocket, message: str) -> None:
    """Send error message to client"""
    try:
        await websocket.send_json({
            "type": "error",
            "message": message,
            "timestamp": asyncio.get_event_loop().time()
        })
    except Exception as e:
        logger.error(f"Failed to send error message: {e}")


# ==================== APPLICATION ENTRY POINT ====================

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
        workers=4,
        loop="asyncio",
        timeout_graceful_shutdown=30
    )