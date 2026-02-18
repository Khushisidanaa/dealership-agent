# Dealership Agent

AI-powered car dealership finder that scrapes listings, compares prices, and autonomously calls/texts dealerships on your behalf.

## Tech Stack

- **Frontend**: React (Vite) + TypeScript
- **Backend**: Python + FastAPI + WebSockets
- **Database**: MongoDB (Motor + Beanie ODM)
- **AI**: OpenAI GPT-4
- **Voice**: Twilio + Deepgram Voice Agent API
- **Dashboard**: KendoReact (Progress Software) -- to be integrated

## Dependency installation

### Backend (Python)

Use a virtual environment so dependencies stay isolated:

```bash
cd backend
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

If `pip` is configured to use a private index (e.g. Artifactory) and the install fails, install from the public PyPI instead:

```bash
pip install -r requirements.txt --index-url https://pypi.org/simple/
```

Copy `.env.example` to `.env` and fill in your API keys.

### Frontend

```bash
cd frontend
npm install
```

---

## Quick Start

### 1. Start MongoDB

```bash
docker compose up -d
```

### 2. Backend

```bash
cd backend
source venv/bin/activate   # if you haven’t created/activated venv yet, see Dependency installation
uvicorn app.main:app --reload --port 8000
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 in your browser.

## Project Structure

```
dealership-agent/
  backend/
    app/
      main.py              # FastAPI app entry point
      config.py            # Environment / settings
      api/                 # Route handlers
        sessions.py
        preferences.py
        chat.py
        search.py
        dashboard.py
        communication.py
        voice.py         # Standalone voice call API (POST /api/voice/call)
        test_drive.py
      services/            # Business logic
        llm_service.py     # OpenAI chat agent
        scraper_service.py # Web scraper (pluggable)
        twilio_service.py  # SMS via Twilio
        deepgram_service.py# Voice calls via Deepgram
        scoring_service.py # Vehicle ranking
      models/
        documents.py       # Beanie ODM documents (MongoDB)
        schemas.py         # Pydantic request/response models
        database.py        # MongoDB connection
    requirements.txt
  frontend/
    src/
      components/          # React components
      services/            # API client + WebSocket
      types/               # TypeScript interfaces
      App.tsx              # Main app with step-based flow
  docker-compose.yml       # MongoDB container
```

## API Endpoints

| Method | Path                                        | Description          |
| ------ | ------------------------------------------- | -------------------- |
| POST   | /api/sessions                               | Create session       |
| POST   | /api/sessions/{id}/preferences              | Submit questionnaire |
| POST   | /api/sessions/{id}/chat                     | Chat with AI agent   |
| GET    | /api/sessions/{id}/chat/history             | Get chat history     |
| POST   | /api/sessions/{id}/search                   | Trigger web scraping |
| GET    | /api/sessions/{id}/search/{sid}/status      | Poll search progress |
| GET    | /api/sessions/{id}/search/{sid}/results     | Get results          |
| POST   | /api/sessions/{id}/shortlist                | Shortlist vehicles   |
| GET    | /api/sessions/{id}/dashboard                | Dashboard data       |
| POST   | /api/sessions/{id}/communication/text       | Send SMS             |
| POST   | /api/sessions/{id}/communication/call       | Start AI voice call (session-based) |
| POST   | /api/voice/call                             | Start AI voice call (standalone, all params) |
| GET    | /api/sessions/{id}/communication/call/{cid} | Call status          |
| POST   | /api/sessions/{id}/test-drive               | Book test drive      |
| GET    | /api/sessions/{id}/test-drive/{bid}         | Booking status       |
| WS     | /ws/sessions/{id}                           | Real-time updates    |

## Environment Variables

Copy `.env.example` to `backend/.env` and fill in:

- `OPENAI_API_KEY` -- for the conversational agent
- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER` -- for SMS/calls
- `DEEPGRAM_API_KEY` -- for voice agent STT/TTS
- `SERVER_BASE_URL` -- **required for voice**: public URL of this backend (e.g. `https://your-ngrok-url.ngrok-free.app`) so Twilio can reach the TwiML and WebSocket

---

## Voice calls (Twilio + Deepgram)

The agent can place **outbound** calls to dealers and hold a conversation using context you pass (e.g. car, budget, availability).

### Standalone voice endpoint (POST /api/voice/call)

Pass in a **prompt** (context from your user conversation) and **start_message** (opening line). No session required.

**How to run (all commands):**

```bash
# Terminal 1: MongoDB
docker compose up -d

# Terminal 2: Backend
cd backend && source venv/bin/activate && uvicorn app.main:app --reload --port 8000

# Terminal 3: ngrok (expose backend for Twilio webhooks)
ngrok http 8000
```

Set `SERVER_BASE_URL` in `backend/.env` to your ngrok URL (e.g. `https://xxx.ngrok-free.app`, no trailing slash). Restart uvicorn if you change it.

```bash
# Terminal 4 (or any): Start a call
curl -X POST http://localhost:8000/api/voice/call \
  -H "Content-Type: application/json" \
  -d '{"to_number": "+15551234567", "prompt": "You are a friendly AI calling a dealership about a 2022 Honda Civic.", "start_message": "Hi, I am calling about the 2022 Honda Civic you have listed."}'
```

**Request body:**

| Param           | Type   | Required | Description                                                        |
|-----------------|--------|----------|--------------------------------------------------------------------|
| `to_number`     | string | Yes      | E.164 phone number to call                                        |
| `prompt`        | string | Yes      | Agent context/instructions (derived from your user conversation)  |
| `start_message` | string | Yes      | Opening line the agent says when the call connects                |

Response: `{ "call_id": "...", "status": "initiating", "to_number": "...", "twiml_url": "..." }`

### Prerequisites

1. **Twilio**
   - Account, phone number, and credentials in `.env`.
   - Twilio will **call your backend** when the outbound call is answered, so the server must be reachable from the internet.

2. **Deepgram**
   - API key (voice agent uses Deepgram for STT/TTS and can use OpenAI for “think” via their managed config).
   - [Deepgram + Twilio guide](https://developers.deepgram.com/docs/twilio-and-deepgram-voice-agent).

3. **Public URL for the backend**
   - Set `SERVER_BASE_URL` in `.env` to the public URL (e.g. `https://abc123.ngrok-free.app`).
   - For local dev, use a tunnel (see below).


