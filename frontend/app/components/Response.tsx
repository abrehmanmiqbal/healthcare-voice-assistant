'use client'

import React, { useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { cn } from '../lib/utils'

interface ResponseProps {
  text: string
  isThinking: boolean
  isSpeaking: boolean
  className?: string
}

export function Response({ text, isThinking, isSpeaking, className }: ResponseProps) {
  const scrollRef = useRef<HTMLDivElement>(null)
  
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [text])
  
  return (
    <div className={cn(
      'glass rounded-2xl p-4 flex flex-col min-h-[200px]',
      className
    )}>
      <div className="flex items-center gap-2 mb-3">
        <span className="text-sm font-medium text-slate-600">
          AI Response
        </span>
        
        {isThinking && (
          <div className="flex items-center gap-1">
            <span className="text-xs text-amber-500">Thinking</span>
            <div className="flex gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-typing-dot" />
              <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-typing-dot" />
              <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-typing-dot" />
            </div>
          </div>
        )}
        
        {isSpeaking && (
          <span className="flex items-center gap-1.5 text-xs text-emerald-500">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
            Speaking
          </span>
        )}
      </div>
      
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto"
      >
        <AnimatePresence mode="wait">
          {text ? (
            <motion.p
              key="response"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="text-slate-700 leading-relaxed"
            >
              {text}
            </motion.p>
          ) : (
            <motion.p
              key="empty"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="text-slate-400 italic text-sm"
            >
              {isThinking ? 'Processing...' : 'AI response will appear here'}
            </motion.p>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}