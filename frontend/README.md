# 🏥 Healthcare Voice AI Assistant

A production-grade, real-time voice AI assistant for healthcare applications with multi-provider support.

## ✨ Features

- 🎙️ **Real-time Voice Interaction** - WebSocket-based bidirectional audio streaming
- 🧠 **Multi-Provider AI** - Groq (primary) with Gemini and OpenAI fallback
- 🎯 **Accurate STT** - Deepgram speech-to-text with streaming support
- 🔊 **Natural TTS** - ElevenLabs text-to-speech with voice customization
- 💾 **Session Management** - Conversation history with automatic cleanup
- 🏥 **Healthcare Focused** - Empathetic responses, medical advice avoidance
- 🔒 **Production Ready** - Error handling, logging, monitoring, rate limiting
- 🎨 **Premium UI** - Glassmorphism design with smooth animations

## 🚀 Quick Start

### Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API keys
python main.py