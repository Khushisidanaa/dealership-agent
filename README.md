# Dealership Agent

AI-powered car dealership finder that scrapes listings, compares prices, and autonomously calls/texts dealerships on your behalf.

## Tech Stack

- **Frontend**: React (Vite) + TypeScript
- **Backend**: Python + FastAPI + WebSockets
- **Database**: MongoDB (Motor + Beanie ODM)
- **AI**: OpenAI GPT-4
- **Voice**: Twilio + Deepgram Voice Agent API
- **Dashboard**: KendoReact (Progress Software) -- to be integrated

## Quick Start

### 1. Start MongoDB

```bash
docker compose up -d
```

### 2. Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill in your API keys
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
| POST   | /api/sessions/{id}/communication/call       | Start AI voice call  |
| GET    | /api/sessions/{id}/communication/call/{cid} | Call status          |
| POST   | /api/sessions/{id}/test-drive               | Book test drive      |
| GET    | /api/sessions/{id}/test-drive/{bid}         | Booking status       |
| WS     | /ws/sessions/{id}                           | Real-time updates    |

## Environment Variables

Copy `.env.example` to `backend/.env` and fill in:

- `OPENAI_API_KEY` -- for the conversational agent
- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER` -- for SMS/calls
- `DEEPGRAM_API_KEY` -- for voice agent STT/TTS
