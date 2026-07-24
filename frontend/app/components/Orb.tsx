'use client'

import React from 'react'
import { motion } from 'framer-motion'
import { Mic, MicOff, Loader2 } from 'lucide-react'
import { cn } from '../lib/utils'

interface OrbProps {
  status: 'idle' | 'listening' | 'thinking' | 'speaking'
  isRecording: boolean
  onClick: () => void
  disabled?: boolean
}

export function Orb({ status, isRecording, onClick, disabled = false }: OrbProps) {
  const getStatusConfig = () => {
    switch (status) {
      case 'listening':
        return {
          bg: 'bg-gradient-to-br from-emerald-400 to-cyan-500',
          ring: 'ring-emerald-400/30',
          animation: 'animate-orb-listening',
          icon: <Mic className="w-8 h-8" />,
          label: 'Listening...',
        }
      case 'thinking':
        return {
          bg: 'bg-gradient-to-br from-amber-400 to-orange-500',
          ring: 'ring-amber-400/30',
          animation: 'animate-orb-pulse',
          icon: <Loader2 className="w-8 h-8 animate-spin" />,
          label: 'Thinking...',
        }
      case 'speaking':
        return {
          bg: 'bg-gradient-to-br from-blue-400 to-indigo-500',
          ring: 'ring-blue-400/30',
          animation: 'animate-orb-speaking',
          icon: <Mic className="w-8 h-8" />,
          label: 'Speaking...',
        }
      default:
        return {
          bg: 'bg-gradient-to-br from-cyan-400 to-blue-500',
          ring: 'ring-cyan-400/20',
          animation: '',
          icon: isRecording ? <Mic className="w-8 h-8" /> : <MicOff className="w-8 h-8" />,
          label: isRecording ? 'Recording' : 'Ready',
        }
    }
  }

  const config = getStatusConfig()

  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className="relative group focus:outline-none"
    >
      <div className={cn(
        'absolute inset-0 rounded-full blur-2xl transition-opacity duration-500',
        status !== 'idle' ? 'opacity-70' : 'opacity-20',
        config.bg
      )} />
      
      <motion.div
        className={cn(
          'relative w-48 h-48 rounded-full flex items-center justify-center',
          'bg-gradient-to-br shadow-2xl text-white',
          'transition-all duration-500',
          config.bg,
          config.animation,
          'ring-4 ring-offset-4 ring-offset-white',
          config.ring,
          disabled && 'opacity-50 cursor-not-allowed',
          !disabled && 'hover:scale-105 cursor-pointer'
        )}
        whileHover={!disabled ? { scale: 1.05 } : {}}
        whileTap={!disabled ? { scale: 0.95 } : {}}
      >
        <div className="relative z-10 flex flex-col items-center gap-2">
          <div className="p-3 rounded-full bg-white/20 backdrop-blur-sm">
            {config.icon}
          </div>
          <span className="text-sm font-medium text-white/90">
            {config.label}
          </span>
        </div>
        
        {/* Ripple effect */}
        {isRecording && (
          <motion.div
            className="absolute inset-0 rounded-full border-2 border-white/30"
            animate={{
              scale: [1, 1.2, 1],
              opacity: [0.5, 0, 0.5],
            }}
            transition={{
              duration: 2,
              repeat: Infinity,
              ease: 'easeInOut',
            }}
          />
        )}
      </motion.div>
    </button>
  )
}