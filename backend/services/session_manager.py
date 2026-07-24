"""
Session Manager - Handles user sessions with conversation history
Thread-safe, memory-efficient session management with TTL
"""

import uuid
import time
import asyncio
import logging
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from datetime import datetime
from collections import deque

logger = logging.getLogger(__name__)


@dataclass
class Session:
    """
    Represents a user session with conversation history and context
    """
    id: str
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    conversation_history: deque = field(default_factory=lambda: deque(maxlen=50))
    context: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    is_active: bool = True
    
    def __post_init__(self):
        """Initialize session with system prompt"""
        self.conversation_history.append({
            "role": "system",
            "content": "You are a compassionate healthcare AI assistant.",
            "timestamp": self.created_at
        })
    
    def update_activity(self) -> None:
        """Update last activity timestamp"""
        self.last_activity = time.time()
    
    def add_message(self, role: str, content: str, metadata: Optional[Dict] = None) -> None:
        """
        Add a message to conversation history
        
        Args:
            role: 'user', 'assistant', or 'system'
            content: Message content
            metadata: Optional metadata for the message
        """
        self.conversation_history.append({
            "role": role,
            "content": content,
            "timestamp": time.time(),
            "metadata": metadata or {}
        })
        self.update_activity()
    
    def get_recent_messages(self, limit: int = 10) -> List[Dict]:
        """
        Get recent conversation messages
        
        Args:
            limit: Maximum number of messages to return
        
        Returns:
            List of recent messages
        """
        messages = list(self.conversation_history)
        return messages[-limit:] if messages else []
    
    def get_context(self, key: str, default: Any = None) -> Any:
        """Get context value by key"""
        return self.context.get(key, default)
    
    def set_context(self, key: str, value: Any) -> None:
        """Set context value"""
        self.context[key] = value
        self.update_activity()
    
    def get_age(self) -> float:
        """Get session age in seconds"""
        return time.time() - self.created_at
    
    def get_inactive_duration(self) -> float:
        """Get inactive duration in seconds"""
        return time.time() - self.last_activity


class SessionManager:
    """
    Manages all active sessions with automatic cleanup and TTL
    Thread-safe implementation with efficient cleanup
    """
    
    def __init__(
        self,
        timeout_seconds: int = 300,
        max_sessions: int = 1000,
        cleanup_interval: int = 60
    ):
        """
        Initialize SessionManager
        
        Args:
            timeout_seconds: Session timeout in seconds
            max_sessions: Maximum concurrent sessions
            cleanup_interval: Cleanup interval in seconds
        """
        self._sessions: Dict[str, Session] = {}
        self.timeout_seconds = timeout_seconds
        self.max_sessions = max_sessions
        self.cleanup_interval = cleanup_interval
        self._lock = asyncio.Lock()
        self._cleanup_task = None
        
        logger.info(f"SessionManager initialized: timeout={timeout_seconds}s, max={max_sessions}")
    
    async def start(self) -> None:
        """Start background cleanup task"""
        if not self._cleanup_task:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("Session cleanup task started")
    
    def create_session(self, metadata: Optional[Dict] = None) -> Session:
        """
        Create a new session
        
        Args:
            metadata: Optional session metadata
        
        Returns:
            New Session object
        """
        # Check session limit
        if len(self._sessions) >= self.max_sessions:
            self.cleanup_expired()  # Try to cleanup expired sessions
            
            if len(self._sessions) >= self.max_sessions:
                raise RuntimeError(f"Maximum sessions reached ({self.max_sessions})")
        
        # Generate session ID
        session_id = str(uuid.uuid4())
        
        # Create session
        session = Session(id=session_id)
        if metadata:
            session.metadata.update(metadata)
        
        # Store session
        self._sessions[session_id] = session
        
        logger.info(f"Session created: {session_id[:8]} | Total: {len(self._sessions)}")
        return session
    
    async def get_session(self, session_id: str) -> Optional[Session]:
        """
        Get session by ID (async version)
        
        Args:
            session_id: Session identifier
        
        Returns:
            Session object or None if not found
        """
        async with self._lock:
            session = self._sessions.get(session_id)
            if session and session.is_active:
                session.update_activity()
                return session
            return None
    
    def get_session_sync(self, session_id: str) -> Optional[Session]:
        """
        Get session by ID (sync version for internal use)
        
        Args:
            session_id: Session identifier
        
        Returns:
            Session object or None if not found
        """
        session = self._sessions.get(session_id)
        if session and session.is_active:
            session.update_activity()
            return session
        return None
    
    async def end_session(self, session_id: str) -> bool:
        """
        End and remove a session
        
        Args:
            session_id: Session identifier
        
        Returns:
            True if session was ended, False otherwise
        """
        async with self._lock:
            session = self._sessions.pop(session_id, None)
            if session:
                session.is_active = False
                logger.info(f"Session ended: {session_id[:8]} | Remaining: {len(self._sessions)}")
                return True
            return False
    
    def cleanup_expired(self) -> int:
        """
        Clean up expired sessions (sync version)
        
        Returns:
            Number of sessions cleaned up
        """
        current_time = time.time()
        expired = []
        
        for session_id, session in self._sessions.items():
            if not session.is_active or (current_time - session.last_activity) > self.timeout_seconds:
                expired.append(session_id)
        
        for session_id in expired:
            self._sessions.pop(session_id, None)
        
        if expired:
            logger.info(f"🧹 Cleaned up {len(expired)} expired sessions | Remaining: {len(self._sessions)}")
        
        return len(expired)
    
    async def _cleanup_loop(self) -> None:
        """Background cleanup loop"""
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval)
                cleaned = self.cleanup_expired()
                if cleaned > 0:
                    logger.debug(f"Background cleanup: removed {cleaned} sessions")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup loop error: {e}")
    
    def get_active_count(self) -> int:
        """Get number of active sessions"""
        return len(self._sessions)
    
    def get_session_stats(self) -> Dict[str, Any]:
        """
        Get session statistics
        
        Returns:
            Dictionary with session statistics
        """
        total = len(self._sessions)
        if total == 0:
            return {"total": 0, "avg_age": 0, "avg_inactive": 0}
        
        ages = [session.get_age() for session in self._sessions.values()]
        inactive = [session.get_inactive_duration() for session in self._sessions.values()]
        
        return {
            "total": total,
            "avg_age": sum(ages) / total,
            "avg_inactive": sum(inactive) / total,
            "max_age": max(ages) if ages else 0,
            "max_inactive": max(inactive) if inactive else 0,
        }
    
    def cleanup(self) -> None:
        """Clean up all resources"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
        
        self._sessions.clear()
        logger.info("SessionManager cleaned up")