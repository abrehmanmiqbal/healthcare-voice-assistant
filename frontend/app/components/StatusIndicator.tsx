
'use client'

import React from 'react'
import { Wifi, WifiOff, Clock } from 'lucide-react'
import { cn } from '../lib/utils'

interface StatusIndicatorProps {
  status: 'connecting' | 'connected' | 'disconnected'
  sessionId: string | null
}

export function StatusIndicator({ status, sessionId }: StatusIndicatorProps) {
  const getStatusConfig = () => {
    switch (status) {
      case 'connected':
        return {
          icon: <Wifi className="w-4 h-4 text-emerald-500" />,
          label: 'Online',
          className: 'bg-emerald-50 text-emerald-700 border-emerald-200'
        }
      case 'connecting':
        return {
          icon: <Clock className="w-4 h-4 text-amber-500 animate-spin" />,
          label: 'Connecting',
          className: 'bg-amber-50 text-amber-700 border-amber-200'
        }
      case 'disconnected':
        return {
          icon: <WifiOff className="w-4 h-4 text-red-500" />,
          label: 'Offline',
          className: 'bg-red-50 text-red-700 border-red-200'
        }
    }
  }

  const config = getStatusConfig()

  return (
    <div className="flex items-center gap-3">
      <div className={cn(
        'flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-sm font-medium',
        config.className
      )}>
        {config.icon}
        <span>{config.label}</span>
      </div>
      
      {sessionId && (
        <span className="text-xs font-mono text-slate-400 bg-slate-50 px-2 py-1 rounded">
          {sessionId.slice(0, 8)}
        </span>
      )}
    </div>
  )
}