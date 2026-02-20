# Dealership Agent

**AI-powered car-shopping assistant** — finds listings, calls and texts dealerships on your behalf, analyzes conversations, and recommends the best matches. Get a PDF report with tips for in-person visits and test drives.

---

## Try it now

**Live demo (hosted on Linode):** [https://tinyurl.com/yd53t4w4](https://tinyurl.com/yd53t4w4)

Scan to open on your phone:

![QR code to live deployment](assets/qr-deployment.png)

---

## What it does

- **Guided flow** — Enter preferences (make, model, budget, location). The agent suggests vehicles and runs real inventory search.
- **Voice & SMS** — Places outbound calls to dealers and sends texts using your context (car, budget, availability).
- **Call analysis** — Summarizes dealer conversations and ranks vehicles so you see the best options.
- **Recommendations** — Picks top vehicles and surfaces requirements that matter for your search.
- **PDF reports** — Generates a report with extra details to keep in mind for in-person visits and test drives. Can also analyze Carfax (or other PDFs) provided by the dealership.

---

## Tech stack

| Layer | Technology |
|-------|------------|
| **Voice (AI)** | [Deepgram](https://deepgram.com/) — STT/TTS for natural dealer calls |
| **Calls & SMS** | [Twilio](https://www.twilio.com/) — outbound calls and texting |
| **Analysis & chat** | **OpenAI GPT-4** — analyzes calls, texts, recommends cards, finds good requirements |
| **PDFs & docs** | [Foxit](https://www.foxit.com/) — PDF generation for user-facing reports; document analysis for Carfax and other dealer-provided PDFs |
| **Backend** | Python, FastAPI, WebSockets |
| **Frontend** | React (Vite), TypeScript |
| **Database** | MongoDB (Motor + Beanie ODM) |

---

## Run locally

### Prerequisites

- **Python 3** (virtual env recommended)
- **Node.js & npm**
- **MongoDB** — use Docker for local, or point to your own deployment

### 1. Get API keys

Ask the devs for the `.env` variables. Copy them into `backend/.env` (you can start from `backend/.env.example`). You’ll need keys for OpenAI, Twilio, Deepgram, and optionally Foxit.

### 2. One-time setup

```bash
# Backend (use a virtual env)
cd backend
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install --index-url https://pypi.org/simple/ -r requirements.txt

# Frontend
cd ../ui
npm install
```

### 3. MongoDB

**Option A — Docker (local):**

```bash
make mongo-local
```

**Option B — Your own Mongo:**  
Set `MONGODB_URI` in `backend/.env` to your deployment.

### 4. Run the app

From the **project root**:

```bash
make deploy      # install deps + build UI (once)
make deploy-run  # start backend + frontend
```

- **Frontend:** http://localhost:5173  
- **Backend (API + docs):** http://localhost:8000  

For API-only local testing: `make mongo-local` then `make run` (backend on port 8000, Mongo on localhost:27017).

---

## API overview

| Method | Path | Description |
|--------|------|-------------|
| **Auth** | | |
| POST | `/api/auth/signup` | Register |
| POST | `/api/auth/login` | Login |
| **Sessions** | | |
| POST | `/api/sessions` | Create session |
| GET | `/api/users/{user_id}/sessions` | List user sessions |
| GET | `/api/sessions/{session_id}/state` | Session state |
| **Agent (orchestrated flow)** | | |
| POST | `/api/agent/start` | Start session + preferences + first message |
| POST | `/api/agent/{session_id}/chat` | Chat |
| POST | `/api/agent/{session_id}/search` | Trigger search |
| POST | `/api/agent/{session_id}/confirm` | Confirm shortlist |
| POST | `/api/agent/{session_id}/testdrive` | Book test drive |
| GET | `/api/agent/{session_id}/state` | Agent state |
| **Preferences & chat** | | |
| POST | `/api/sessions/{session_id}/preferences` | Submit preferences |
| POST | `/api/sessions/{session_id}/chat` | Chat message |
| GET | `/api/sessions/{session_id}/chat/history` | Chat history |
| **Search & listings** | | |
| POST | `/api/sessions/{session_id}/search` | Trigger search |
| GET | `/api/sessions/{session_id}/search/{search_id}/status` | Search status |
| GET | `/api/sessions/{session_id}/search/{search_id}/results` | Search results |
| GET | `/api/sessions/{session_id}/search/cars` | Cars list |
| GET | `/api/listings/by-session/{session_id}` | Listings by session |
| POST | `/api/listings/search` | Listings search |
| **Dashboard** | | |
| POST | `/api/sessions/{session_id}/shortlist` | Shortlist vehicles |
| GET | `/api/sessions/{session_id}/dashboard` | Dashboard data |
| GET | `/api/sessions/{session_id}/export-pdf` | Export dashboard PDF (Foxit) |
| **Analyze & recommendations** | | |
| POST | `/api/sessions/{session_id}/analyze` | Call dealers, summarize, rank (SSE) |
| POST | `/api/sessions/{session_id}/recommendations/pick-best-two` | Pick best two |
| **Test drive** | | |
| POST | `/api/sessions/{session_id}/test-drive` | Create booking |
| POST | `/api/sessions/{session_id}/test-drive/call` | Trigger call |
| GET | `/api/sessions/{session_id}/test-drive/{booking_id}` | Booking status |
| **Voice (standalone)** | | |
| POST | `/api/voice/call` | Start outbound AI voice call |
| GET | `/api/voice/call/{call_id}` | Call status |
| **Users** | | |
| PUT | `/api/users/{user_id}/requirements` | Update user requirements |
| **Health** | | |
| GET | `/health` | Health check |

---

## Makefile commands

| Command | Description |
|---------|-------------|
| `make help` | List all targets |
| `make mongo-local` | Start MongoDB on localhost:27017 |
| `make mongo` | Start MongoDB via docker compose (internal) |
| `make install` | Install backend deps (public PyPI) |
| `make run` | Start FastAPI on port 8000 (needs Mongo on 27017) |
| `make build-ui` | Build React UI to `ui/dist` |
| `make deploy` | Install backend deps + build UI |
| `make deploy-run` | Run backend + frontend (0.0.0.0 for local/Linode) |
| `make stop` | Stop Docker stack |

---

## Environment variables (summary)

In `backend/.env` (get values from devs or `.env.example`):

- **OpenAI** — `OPENAI_API_KEY`
- **Twilio** — `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`
- **Deepgram** — `DEEPGRAM_API_KEY`
- **Foxit** — `FOXIT_CLIENT_ID`, `FOXIT_CLIENT_SECRET`, `FOXIT_API_HOST` (optional)
- **Server** — `SERVER_BASE_URL` (public backend URL for Twilio webhooks; e.g. ngrok for local)
- **MongoDB** — `MONGODB_URI` (optional; default/local uses Docker)

---

*Built for the hackathon — happy judging.*
