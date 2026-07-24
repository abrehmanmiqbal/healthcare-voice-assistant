'use client'

import { useState, useEffect, useRef, useCallback } from 'react'

interface WebSocketHook {
  sendMessage: (data: any) => void
  lastMessage: MessageEvent | null
  readyState: number
  connect: () => void
  disconnect: () => void
}

export function useWebSocket(url: string): WebSocketHook {
  const [lastMessage, setLastMessage] = useState<MessageEvent | null>(null)
  const [readyState, setReadyState] = useState<number>(WebSocket.CONNECTING)
  
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectAttemptsRef = useRef(0)
  const maxReconnectAttempts = 5
  const reconnectDelay = 3000

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return
    }

    try {
      const ws = new WebSocket(url)
      wsRef.current = ws

      ws.onopen = () => {
        console.log('WebSocket connected')
        setReadyState(WebSocket.OPEN)
        reconnectAttemptsRef.current = 0
      }

      ws.onmessage = (event) => {
        setLastMessage(event)
      }

      ws.onclose = (event) => {
        console.log('WebSocket closed:', event.code, event.reason)
        setReadyState(WebSocket.CLOSED)
        
        // Auto-reconnect
        if (reconnectAttemptsRef.current < maxReconnectAttempts) {
          reconnectAttemptsRef.current++
          console.log(`Reconnecting in ${reconnectDelay}ms... (Attempt ${reconnectAttemptsRef.current})`)
          setTimeout(() => {
            connect()
          }, reconnectDelay)
        } else {
          console.error('Max reconnect attempts reached')
        }
      }

      ws.onerror = (error) => {
        console.error('WebSocket error:', error)
        ws.close()
      }
    } catch (error) {
      console.error('Failed to connect WebSocket:', error)
      setReadyState(WebSocket.CLOSED)
    }
  }, [url])

  const disconnect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
    setReadyState(WebSocket.CLOSED)
  }, [])

  const sendMessage = useCallback((data: any) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      const message = typeof data === 'string' ? data : JSON.stringify(data)
      wsRef.current.send(message)
    } else {
      console.warn('WebSocket is not open. Message not sent:', data)
    }
  }, [])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      disconnect()
    }
  }, [disconnect])

  return {
    sendMessage,
    lastMessage,
    readyState,
    connect,
    disconnect,
  }
}