'use client'

import React, { useState, useEffect, useCallback, useRef } from 'react'
import { motion } from 'framer-motion'
import { Mic, Square, Wifi, WifiOff } from 'lucide-react'
import { cn } from '@/lib/utils'

type ConnectionStatus = 'connecting' | 'connected' | 'disconnected'
type VoiceStatus = 'idle' | 'listening' | 'thinking' | 'speaking'

export function VoiceAssistant() {
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('connecting')
  const [voiceStatus, setVoiceStatus] = useState<VoiceStatus>('idle')
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [transcript, setTranscript] = useState('')
  const [response, setResponse] = useState('')
  const [isRecording, setIsRecording] = useState(false)
  
  const wsRef = useRef<WebSocket | null>(null)
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const audioChunksRef = useRef<Blob[]>([])

  // WebSocket connection
  useEffect(() => {
    const wsUrl = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000/ws'
    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onopen = () => {
      setConnectionStatus('connected')
      console.log('✅ WebSocket connected')
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        handleMessage(data)
      } catch (error) {
        console.error('Failed to parse message:', error)
      }
    }

    ws.onclose = () => {
      setConnectionStatus('disconnected')
      console.log('❌ WebSocket disconnected')
      setTimeout(() => {
        if (wsRef.current?.readyState !== WebSocket.OPEN) {
          // Reconnect
        }
      }, 3000)
    }

    ws.onerror = (error) => {
      console.error('WebSocket error:', error)
    }

    return () => {
      if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
        ws.close()
      }
    }
  }, [])

  const handleMessage = (data: any) => {
    console.log('📨 Received:', data.type)
    switch (data.type) {
      case 'session':
        setSessionId(data.session_id)
        break
      case 'status':
        setVoiceStatus(data.status)
        break
      case 'transcript':
        setTranscript(data.text)
        break
      case 'response':
        setResponse(data.text)
        break
      case 'tts':
        // Handle TTS audio
        playAudio(data.audio)
        break
      case 'error':
        console.error('Server error:', data.message)
        break
    }
  }

  const playAudio = useCallback((base64Audio: string) => {
    try {
      const audioData = atob(base64Audio)
      const arrayBuffer = new ArrayBuffer(audioData.length)
      const view = new Uint8Array(arrayBuffer)
      for (let i = 0; i < audioData.length; i++) {
        view[i] = audioData.charCodeAt(i)
      }
      
      const blob = new Blob([arrayBuffer], { type: 'audio/webm' })
      const url = URL.createObjectURL(blob)
      const audio = new Audio(url)
      
      audio.onended = () => {
        URL.revokeObjectURL(url)
        setVoiceStatus('idle')
      }
      
      audio.onerror = () => {
        console.error('Audio playback error')
        URL.revokeObjectURL(url)
        setVoiceStatus('idle')
      }
      
      audio.play()
    } catch (error) {
      console.error('Failed to play audio:', error)
      setVoiceStatus('idle')
    }
  }, [])

  const startRecording = useCallback(async () => {
    try {
      console.log('🎤 Starting recording...')
      
      const stream = await navigator.mediaDevices.getUserMedia({ 
        audio: { 
          echoCancellation: true, 
          noiseSuppression: true,
          autoGainControl: true,
          sampleRate: 16000,
          channelCount: 1,
        } 
      })
      streamRef.current = stream

      // Find supported MIME type
      let mimeType = 'audio/webm;codecs=opus'
      if (!MediaRecorder.isTypeSupported(mimeType)) {
        mimeType = 'audio/webm'
      }
      if (!MediaRecorder.isTypeSupported(mimeType)) {
        mimeType = 'audio/mp4'
      }
      console.log(`📹 Using MIME type: ${mimeType}`)

      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: mimeType,
      })
      mediaRecorderRef.current = mediaRecorder
      audioChunksRef.current = []

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data)
          
          if (wsRef.current?.readyState === WebSocket.OPEN) {
            const reader = new FileReader()
            reader.onload = () => {
              const base64 = (reader.result as string).split(',')[1]
              wsRef.current?.send(JSON.stringify({
                type: 'audio',
                data: base64
              }))
            }
            reader.readAsDataURL(event.data)
          }
        }
      }

      mediaRecorder.start(1000) // Send chunks every 1 second
      setIsRecording(true)
      setVoiceStatus('listening')
      setTranscript('')
      setResponse('')

      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: 'start' }))
        console.log('📤 Sent start message')
      }
    } catch (error) {
      console.error('Failed to start recording:', error)
      alert('Please allow microphone access.')
    }
  }, [])

  const stopRecording = useCallback(() => {
    console.log('🛑 Stopping recording...')
    
    if (mediaRecorderRef.current?.state === 'recording') {
      mediaRecorderRef.current.stop()
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop())
      streamRef.current = null
    }
    setIsRecording(false)
    setVoiceStatus('thinking')

    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'stop' }))
      console.log('📤 Sent stop message')
    }
  }, [])

  const toggleRecording = useCallback(() => {
    if (connectionStatus !== 'connected') {
      console.warn('⚠️ Not connected to server')
      return
    }
    if (isRecording) {
      stopRecording()
    } else {
      startRecording()
    }
  }, [isRecording, startRecording, stopRecording, connectionStatus])

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <header className="flex items-center justify-between p-4 mb-4 bg-white/70 backdrop-blur-xl rounded-2xl border border-white/20 shadow-lg">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-gradient-to-br from-cyan-400 to-blue-500 flex items-center justify-center text-white text-xl">
            🏥
          </div>
          <div>
            <h1 className="text-xl font-semibold text-slate-800 tracking-tight">HealthVoice</h1>
            <p className="text-xs text-slate-500">Healthcare AI Assistant</p>
          </div>
        </div>
        
        <div className="flex items-center gap-3">
          <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-sm font-medium ${
            connectionStatus === 'connected' 
              ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
              : connectionStatus === 'connecting'
              ? 'bg-amber-50 text-amber-700 border-amber-200'
              : 'bg-red-50 text-red-700 border-red-200'
          }`}>
            {connectionStatus === 'connected' ? <Wifi className="w-4 h-4" /> : <WifiOff className="w-4 h-4" />}
            <span>{connectionStatus === 'connected' ? 'Online' : connectionStatus === 'connecting' ? 'Connecting' : 'Offline'}</span>
          </div>
          
          {sessionId && (
            <span className="text-xs font-mono text-slate-400 bg-slate-50 px-2 py-1 rounded">
              {sessionId.slice(0, 8)}
            </span>
          )}
          
          <button
            onClick={toggleRecording}
            disabled={connectionStatus !== 'connected'}
            className={cn(
              "p-3 rounded-full transition-all duration-300",
              isRecording
                ? "bg-red-500 hover:bg-red-600 text-white shadow-lg shadow-red-200"
                : "bg-gradient-to-r from-cyan-500 to-blue-500 hover:from-cyan-600 hover:to-blue-600 text-white shadow-lg shadow-cyan-200",
              connectionStatus !== 'connected' && "opacity-50 cursor-not-allowed"
            )}
          >
            {isRecording ? <Square className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
          </button>
        </div>
      </header>

      {/* Main Content */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-3 gap-4 min-h-0">
        {/* Orb */}
        <div className="lg:col-span-1 flex flex-col items-center justify-center p-4 bg-white/70 backdrop-blur-xl rounded-2xl border border-white/20 shadow-lg">
          <motion.div
            className={cn(
              "relative w-48 h-48 rounded-full flex items-center justify-center",
              "bg-gradient-to-br from-cyan-400 to-blue-500 shadow-2xl text-white",
              voiceStatus === 'listening' && "animate-pulse",
              voiceStatus === 'speaking' && "animate-bounce"
            )}
            animate={{
              scale: voiceStatus === 'listening' ? [1, 0.95, 1] : voiceStatus === 'speaking' ? [1, 1.05, 1] : 1
            }}
            transition={{ duration: 1.2, repeat: Infinity }}
          >
            <div className="relative z-10 flex flex-col items-center gap-2">
              <div className="p-3 rounded-full bg-white/20 backdrop-blur-sm">
                <Mic className="w-8 h-8" />
              </div>
              <span className="text-sm font-medium text-white/90">
                {voiceStatus === 'listening' ? 'Listening...' : 
                 voiceStatus === 'thinking' ? 'Thinking...' :
                 voiceStatus === 'speaking' ? 'Speaking...' : 
                 isRecording ? 'Recording' : 'Ready'}
              </span>
            </div>
          </motion.div>
          
          <div className="mt-4 text-center">
            <p className="text-xs text-slate-400">
              {isRecording ? 'Recording... Speak clearly!' : 'Click the mic to start'}
            </p>
          </div>
        </div>

        {/* Transcript & Response */}
        <div className="lg:col-span-2 flex flex-col gap-4 min-h-0">
          <div className="flex-1 bg-white/70 backdrop-blur-xl rounded-2xl border border-white/20 shadow-lg p-4 overflow-y-auto min-h-[150px]">
            <div className="flex items-center gap-2 mb-3">
              <span className="text-sm font-medium text-slate-600">Live Transcript</span>
              {voiceStatus === 'listening' && (
                <span className="flex items-center gap-1.5 text-xs text-cyan-500">
                  <span className="w-1.5 h-1.5 rounded-full bg-cyan-500 animate-pulse" />
                  Recording
                </span>
              )}
            </div>
            <div>
              {transcript ? (
                <p className="text-slate-700 leading-relaxed">{transcript}</p>
              ) : (
                <p className="text-slate-400 italic text-sm">
                  {voiceStatus === 'listening' ? 'Listening... Speak now!' : 'Your speech will appear here'}
                </p>
              )}
            </div>
          </div>

          <div className="flex-1 bg-white/70 backdrop-blur-xl rounded-2xl border border-white/20 shadow-lg p-4 overflow-y-auto min-h-[150px]">
            <div className="flex items-center gap-2 mb-3">
              <span className="text-sm font-medium text-slate-600">AI Response</span>
              {voiceStatus === 'thinking' && (
                <div className="flex gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-bounce" />
                  <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-bounce [animation-delay:0.2s]" />
                  <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-bounce [animation-delay:0.4s]" />
                </div>
              )}
              {voiceStatus === 'speaking' && (
                <span className="flex items-center gap-1.5 text-xs text-emerald-500">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                  Speaking
                </span>
              )}
            </div>
            <div>
              {response ? (
                <p className="text-slate-700 leading-relaxed">{response}</p>
              ) : (
                <p className="text-slate-400 italic text-sm">
                  {voiceStatus === 'thinking' ? 'Processing...' : 'AI response will appear here'}
                </p>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Footer */}
      <footer className="mt-4 p-3 text-center text-xs text-slate-400 bg-white/70 backdrop-blur-xl rounded-2xl border border-white/20 shadow-lg">
        <p>
          Session {sessionId ? `#${sessionId.slice(0, 8)}` : 'connecting...'}
          {' • '}
          Powered by Groq AI & Deepgram STT
        </p>
      </footer>
    </div>
  )
}