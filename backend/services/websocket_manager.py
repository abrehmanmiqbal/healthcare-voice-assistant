
"""
WebSocket Manager - Manages WebSocket connections with connection pooling
Supports broadcasting, load balancing, and graceful disconnections
"""

import asyncio
import logging
from typing import Dict, Set, Optional, List, Any
from fastapi import WebSocket
from dataclasses import dataclass, field
import time

logger = logging.getLogger(__name__)


@dataclass
class ConnectionInfo:
    """Information about a WebSocket connection"""
    websocket: WebSocket
    session_id: str
    connected_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    is_active: bool = True
    
    def update_activity(self) -> None:
        """Update last activity timestamp"""
        self.last_activity = time.time()


class WebSocketManager:
    """
    Manages WebSocket connections with connection pooling and broadcasting
    """
    
    def __init__(self, max_connections: int = 1000):
        """
        Initialize WebSocketManager
        
        Args:
            max_connections: Maximum concurrent WebSocket connections
        """
        self._connections: Dict[str, ConnectionInfo] = {}
        self._session_to_connection: Dict[str, str] = {}  # session_id -> connection_id
        self.max_connections = max_connections
        self._lock = asyncio.Lock()
        self._heartbeat_task = None
        
        logger.info(f"WebSocketManager initialized: max_connections={max_connections}")
    
    async def start(self) -> None:
        """Start background heartbeat task"""
        if not self._heartbeat_task:
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            logger.info("WebSocket heartbeat task started")
    
    async def register(
        self,
        session_id: str,
        websocket: WebSocket,
        metadata: Optional[Dict] = None
    ) -> str:
        """
        Register a WebSocket connection
        
        Args:
            session_id: Session ID
            websocket: WebSocket connection
            metadata: Optional connection metadata
        
        Returns:
            Connection ID
        """
        async with self._lock:
            # Check connection limit
            if len(self._connections) >= self.max_connections:
                raise RuntimeError(f"Maximum connections reached ({self.max_connections})")
            
            # Create connection info
            connection_id = f"conn_{session_id}_{int(time.time())}"
            connection_info = ConnectionInfo(
                websocket=websocket,
                session_id=session_id,
                metadata=metadata or {}
            )
            
            # Store connection
            self._connections[connection_id] = connection_info
            self._session_to_connection[session_id] = connection_id
            
            logger.info(f"WebSocket registered: {connection_id[:8]} | Total: {len(self._connections)}")
            return connection_id
    
    async def unregister(self, session_id: str) -> bool:
        """
        Unregister a WebSocket connection
        
        Args:
            session_id: Session ID
        
        Returns:
            True if unregistered, False otherwise
        """
        async with self._lock:
            connection_id = self._session_to_connection.pop(session_id, None)
            if connection_id:
                connection_info = self._connections.pop(connection_id, None)
                if connection_info:
                    connection_info.is_active = False
                    try:
                        await connection_info.websocket.close()
                    except Exception as e:
                        logger.debug(f"Error closing websocket: {e}")
                    
                    logger.info(f"WebSocket unregistered: {connection_id[:8]} | Remaining: {len(self._connections)}")
                    return True
            return False
    
    def get_connection(self, session_id: str) -> Optional[ConnectionInfo]:
        """
        Get connection info by session ID
        
        Args:
            session_id: Session ID
        
        Returns:
            ConnectionInfo or None
        """
        connection_id = self._session_to_connection.get(session_id)
        if connection_id:
            return self._connections.get(connection_id)
        return None
    
    async def send_message(
        self,
        session_id: str,
        message: Dict[str, Any],
        retry: int = 3
    ) -> bool:
        """
        Send a message to a specific session
        
        Args:
            session_id: Session ID
            message: Message to send
            retry: Number of retry attempts
        
        Returns:
            True if message sent successfully
        """
        connection_info = self.get_connection(session_id)
        if not connection_info or not connection_info.is_active:
            return False
        
        websocket = connection_info.websocket
        
        for attempt in range(retry):
            try:
                await websocket.send_json(message)
                connection_info.update_activity()
                return True
            except Exception as e:
                if attempt < retry - 1:
                    await asyncio.sleep(0.5)
                    continue
                logger.error(f"Failed to send message to {session_id[:8]}: {e}")
                return False
        
        return False
    
    async def broadcast(
        self,
        message: Dict[str, Any],
        exclude: Optional[Set[str]] = None
    ) -> Dict[str, bool]:
        """
        Broadcast message to all connected sessions
        
        Args:
            message: Message to broadcast
            exclude: Set of session IDs to exclude
        
        Returns:
            Dict of session_id -> success status
        """
        if exclude is None:
            exclude = set()
        
        results = {}
        tasks = []
        
        for session_id in self._session_to_connection.keys():
            if session_id not in exclude:
                tasks.append(self.send_message(session_id, message))
        
        if tasks:
            results_list = await asyncio.gather(*tasks, return_exceptions=True)
            for i, session_id in enumerate(session_id for session_id in self._session_to_connection.keys() if session_id not in exclude):
                results[session_id] = not isinstance(results_list[i], Exception)
        
        return results
    
    async def _heartbeat_loop(self) -> None:
        """Background heartbeat to keep connections alive"""
        while True:
            try:
                await asyncio.sleep(15)  # Heartbeat interval
                
                # Send heartbeat to all connections
                heartbeat_message = {
                    "type": "heartbeat",
                    "timestamp": time.time()
                }
                
                for session_id in list(self._session_to_connection.keys()):
                    await self.send_message(session_id, heartbeat_message)
                
                # Clean up stale connections
                await self._cleanup_stale_connections()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat loop error: {e}")
    
    async def _cleanup_stale_connections(self) -> None:
        """Clean up stale connections (inactive for > 60 seconds)"""
        stale_threshold = 60  # seconds
        current_time = time.time()
        stale = []
        
        for connection_id, connection_info in self._connections.items():
            if current_time - connection_info.last_activity > stale_threshold:
                stale.append((connection_id, connection_info.session_id))
        
        for connection_id, session_id in stale:
            logger.warning(f"Removing stale connection: {connection_id[:8]} | Session: {session_id[:8]}")
            await self.unregister(session_id)
    
    def get_connection_count(self) -> int:
        """Get number of active connections"""
        return len(self._connections)
    
    def get_session_ids(self) -> List[str]:
        """Get all active session IDs"""
        return list(self._session_to_connection.keys())
    
    def get_stats(self) -> Dict[str, Any]:
        """Get connection statistics"""
        total = len(self._connections)
        if total == 0:
            return {"total": 0, "avg_age": 0}
        
        ages = [time.time() - conn.connected_at for conn in self._connections.values()]
        
        return {
            "total": total,
            "avg_age": sum(ages) / total,
            "max_connections": self.max_connections,
            "utilization": (total / self.max_connections) * 100,
        }
    
    async def cleanup(self) -> None:
        """Clean up all resources"""
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        
        # Close all connections
        for connection_id, connection_info in list(self._connections.items()):
            try:
                await connection_info.websocket.close()
            except Exception:
                pass
        
        self._connections.clear()
        self._session_to_connection.clear()
        logger.info("WebSocketManager cleaned up")