# Healthcare Voice AI Assistant

A production-ready AI-powered Healthcare Voice Assistant built with FastAPI and a lightweight HTML frontend. The application enables real-time voice conversations using Speech-to-Text (STT), Large Language Models (LLMs), and Text-to-Speech (TTS).

---

## Features

- Real-time Voice Interaction
- AI-powered Healthcare Conversations
- WebSocket-based Streaming
- Speech-to-Text (STT)
- Large Language Model (LLM) Integration
- Text-to-Speech (TTS)
- Health Monitoring Endpoints
- Environment Variable Support
- Modular Backend Architecture

---

## Tech Stack

### Backend

- FastAPI
- Uvicorn
- WebSockets
- Python 3.12

### AI Services

- Groq
- Deepgram
- ElevenLabs

### Frontend

- HTML
- CSS
- JavaScript

---

## Project Structure

```text
healthcare-voice-assistant/
│
├── backend/
│   ├── main.py
│   ├── config.py
│   ├── requirements.txt
│   ├── services/
│   └── .env.example
│
├── frontend/
│   └── index.html
│
├── .gitignore
└── README.md
```

---

## Installation

Clone the repository:

```bash
git clone https://github.com/abrehmanmiqbal/healthcare-voice-assistant.git
```

Navigate to the backend directory:

```bash
cd healthcare-voice-assistant/backend
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create a `.env` file:

```env
GROQ_API_KEY=your_api_key
DEEPGRAM_API_KEY=your_api_key
ELEVENLABS_API_KEY=your_api_key
```

Run the backend:

```bash
python main.py
```

Open the frontend:

```
frontend/index.html
```

---

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `/health` | Health Check |
| `/health/liveness` | Liveness Probe |
| `/health/readiness` | Readiness Probe |
| `/ws` | WebSocket Endpoint |

---

## Deployment

**Frontend:** Cloudflare Pages

**Backend:** FastAPI-compatible hosting (configure environment variables and use the platform's recommended Uvicorn start command).

---

## Environment Variables

```env
GROQ_API_KEY=
DEEPGRAM_API_KEY=
ELEVENLABS_API_KEY=
```

---

## License

This project is provided for educational and portfolio purposes.

---

## Author

**Abdul Rehman**

AI Engineer

GitHub: https://github.com/abrehmanmiqbal