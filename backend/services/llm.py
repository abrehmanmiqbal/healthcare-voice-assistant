"""
LLM Service - Manages Large Language Model interactions
Supports multiple providers with fallback and load balancing
"""

import asyncio
import json
import time
import logging
from typing import List, Dict, Any, Optional, Tuple
from enum import Enum
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class LLMProvider:
    """LLM provider types"""
    GROQ = "groq"
    GEMINI = "gemini"
    OPENAI = "openai"


class LLMService:
    """
    Unified LLM service with provider abstraction and fallback
    """
    
    SYSTEM_PROMPT = """You are a compassionate healthcare AI assistant. Your role is to:
1. Be empathetic and understanding in all responses
2. Provide concise responses (1-2 sentences when possible)
3. Ask clarifying questions when needed
4. Never provide specific medical advice or diagnoses
5. Always recommend consulting a healthcare professional when appropriate
6. Use clear, accessible language without markdown or special characters
7. Maintain a warm, professional tone
8. If uncertain, acknowledge it and suggest professional consultation

Remember: You are not a doctor. Your purpose is to support and guide users toward proper healthcare resources."""
    
    def __init__(self, provider: str = "groq"):
        """
        Initialize LLM Service
        
        Args:
            provider: Primary LLM provider
        """
        self.provider = provider
        self.providers = {
            LLMProvider.GROQ: self._groq_completion,
            LLMProvider.GEMINI: self._gemini_completion,
            LLMProvider.OPENAI: self._openai_completion,
        }
        self.fallback_providers = [LLMProvider.GEMINI, LLMProvider.OPENAI]
        self._client = None
        self._initialized = False
        
        # Rate limiting
        self._request_timestamps = []
        self._rate_limit = 50  # requests per minute
        self._rate_limit_window = 60  # seconds
        
        logger.info(f"LLM Service initialized: provider={provider}")
    
    async def initialize(self) -> None:
        """Initialize HTTP client"""
        if not self._client:
            self._client = httpx.AsyncClient(
                timeout=settings.llm_timeout,
                limits=httpx.Limits(max_keepalive_connections=20, max_connections=100)
            )
            self._initialized = True
            logger.info("LLM HTTP client initialized")
    
    async def generate_response(
        self,
        user_message: str,
        conversation_history: List[Dict],
        session_id: str
    ) -> str:
        """
        Generate response using primary provider with fallback
        
        Args:
            user_message: User's message
            conversation_history: Previous conversation messages
            session_id: Session ID for context
        
        Returns:
            AI response text
        """
        if not self._initialized:
            await self.initialize()
        
        # Rate limiting
        if not self._check_rate_limit():
            logger.warning("Rate limit exceeded, waiting...")
            await asyncio.sleep(1)
        
        # Prepare messages
        messages = self._prepare_messages(user_message, conversation_history)
        
        # Try primary provider
        try:
            response = await self.providers[self.provider](messages)
            if response:
                return response
        except Exception as e:
            logger.error(f"Primary provider {self.provider} failed: {e}")
        
        # Try fallback providers
        if settings.llm_fallback_enabled:
            for fallback in self.fallback_providers:
                if fallback == self.provider:
                    continue
                try:
                    logger.info(f"Attempting fallback to {fallback}")
                    response = await self.providers[fallback](messages)
                    if response:
                        return response
                except Exception as e:
                    logger.error(f"Fallback {fallback} failed: {e}")
                    continue
        
        # All providers failed
        return "I'm having trouble processing your request. Please try again in a moment. If this persists, please consult a healthcare professional directly."
    
    def _prepare_messages(self, user_message: str, history: List[Dict]) -> List[Dict]:
        """Prepare messages for LLM API"""
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT}
        ]
        
        # Add recent history (excluding system messages)
        for msg in history:
            if msg.get("role") in ["user", "assistant"]:
                messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
        
        # Add current message
        messages.append({"role": "user", "content": user_message})
        
        return messages
    
    def _check_rate_limit(self) -> bool:
        """Check if rate limit is exceeded"""
        current_time = time.time()
        self._request_timestamps = [
            t for t in self._request_timestamps
            if current_time - t < self._rate_limit_window
        ]
        
        if len(self._request_timestamps) >= self._rate_limit:
            return False
        
        self._request_timestamps.append(current_time)
        return True
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(httpx.HTTPStatusError)
    )
    async def _groq_completion(self, messages: List[Dict]) -> Optional[str]:
        """Call Groq API with latest model"""
        if not settings.groq_api_key:
            logger.warning("Groq API key not configured")
            return None
        
        try:
            # Using the latest available Groq model
            model = getattr(settings, 'llm_model', 'llama-3.1-8b-instant')
            
            response = await self._client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.groq_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": settings.llm_temperature,
                    "max_tokens": settings.llm_max_tokens,
                    "top_p": 0.95,
                }
            )
            response.raise_for_status()
            data = response.json()
            
            # Validate response
            if "choices" in data and data["choices"]:
                content = data["choices"][0].get("message", {}).get("content", "")
                return self._clean_response(content)
            
            return None
            
        except httpx.HTTPStatusError as e:
            logger.error(f"Groq API error: {e.response.status_code} - {e.response.text[:200]}")
            raise
        except Exception as e:
            logger.error(f"Groq completion error: {e}")
            raise
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(httpx.HTTPStatusError)
    )
    async def _gemini_completion(self, messages: List[Dict]) -> Optional[str]:
        """Call Gemini API with updated endpoint"""
        if not settings.gemini_api_key:
            logger.warning("Gemini API key not configured")
            return None
        
        try:
            # Convert messages to Gemini format
            prompt = self._format_for_gemini(messages)
            
            # Using v1 API with gemini-1.5-flash model
            response = await self._client.post(
                f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={settings.gemini_api_key}",
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": settings.llm_temperature,
                        "maxOutputTokens": settings.llm_max_tokens,
                        "topP": 0.95,
                        "topK": 40
                    },
                    "safetySettings": [
                        {
                            "category": "HARM_CATEGORY_MEDICAL",
                            "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                        }
                    ]
                }
            )
            response.raise_for_status()
            data = response.json()
            
            if "candidates" in data and data["candidates"]:
                content = data["candidates"][0].get("content", {}).get("parts", [{}])[0].get("text", "")
                return self._clean_response(content)
            
            return None
            
        except httpx.HTTPStatusError as e:
            logger.error(f"Gemini API error: {e.response.status_code}")
            if e.response.status_code == 404:
                logger.error("Model not found. Try using 'gemini-1.5-pro' or 'gemini-1.0-pro'")
            raise
        except Exception as e:
            logger.error(f"Gemini completion error: {e}")
            raise
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(httpx.HTTPStatusError)
    )
    async def _openai_completion(self, messages: List[Dict]) -> Optional[str]:
        """Call OpenAI API"""
        if not settings.openai_api_key:
            logger.warning("OpenAI API key not configured")
            return None
        
        try:
            response = await self._client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.openai_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "gpt-3.5-turbo",
                    "messages": messages,
                    "temperature": settings.llm_temperature,
                    "max_tokens": settings.llm_max_tokens,
                }
            )
            response.raise_for_status()
            data = response.json()
            
            if "choices" in data and data["choices"]:
                content = data["choices"][0].get("message", {}).get("content", "")
                return self._clean_response(content)
            
            return None
            
        except httpx.HTTPStatusError as e:
            logger.error(f"OpenAI API error: {e.response.status_code}")
            raise
        except Exception as e:
            logger.error(f"OpenAI completion error: {e}")
            raise
    
    def _format_for_gemini(self, messages: List[Dict]) -> str:
        """Format messages for Gemini API"""
        formatted = []
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            if role == "system":
                formatted.append(f"Instruction: {content}")
            elif role == "user":
                formatted.append(f"User: {content}")
            elif role == "assistant":
                formatted.append(f"Assistant: {content}")
        
        return "\n\n".join(formatted)
    
    def _clean_response(self, text: str) -> str:
        """Clean and format response text"""
        if not text:
            return ""
        
        # Remove markdown symbols
        text = text.replace("**", "").replace("__", "").replace("`", "")
        
        # Remove special characters
        text = text.replace("*", "").replace("#", "").replace(">", "")
        
        # Remove extra whitespace
        text = " ".join(text.split())
        
        # Ensure proper sentence structure
        text = text.strip()
        if text and not text.endswith((".", "!", "?")):
            text += "."
        
        return text
    
    async def cleanup(self) -> None:
        """Clean up resources"""
        if self._client:
            await self._client.aclose()
            self._client = None
            self._initialized = False
            logger.info("LLM Service cleaned up")