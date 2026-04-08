# Dealership Agent

AI-powered car-shopping assistant that gathers your requirements, searches real inventory (cars.com, Facebook Marketplace), validates listings with image analysis, and can call dealerships on your behalf. The agent confirms details with dealers, assesses their responses, and recommends vehicles. Test-drive booking is supported with a background-check PDF report for the make and model.

---

## Try it now

**Live demo:** [https://tinyurl.com/znbbpbwd](https://tinyurl.com/znbbpbwd)

To deploy on **AWS EC2**: see [docs/deploy-aws.md](docs/deploy-aws.md).

Scan to open on your phone:

![QR code to live deployment](assets/qr-deployment.svg)

---

## How it works

**Requirements.** A foundation model on AWS (DeepSeek via Amazon Bedrock) gathers and refines your preferences: make, model, budget, location, and other criteria.

**Search.** Car search is handled by Nova Act. It queries cars.com and Facebook Marketplace for vehicles that match your requirements.

**Image validation.** The DeepSeek foundation model reviews listing images to check for issues and alignment with your requirements. Listings that do not match or show problems are rejected at this stage.

**Results.** Data returned by Nova Act is scrubbed, parsed, and shown in the UI so you can browse and shortlist.

**Dealer calls.** If you choose to call a dealership, the app uses Nova Sonic and Twilio to place the call. An AI agent speaks to the dealer, confirms vehicle details, and performs a structured check: it assesses what the dealer says (accuracy and consistency), asks pointed questions, and evaluates their attitude. The agent summarizes the conversation and surfaces the results. It recommends which vehicles are worth your time to check out in person.

**Test drive.** If you want to schedule a test drive, the agent calls the dealership on your behalf to set up the appointment. Once the test drive is confirmed, the DeepSeek model runs a background check on the make and model of the vehicle. It produces a detailed PDF report for you to use at the dealership: points of interest on the car, known issues for that model, recalls to verify in person, and other items to inspect during the test drive.

---

## Tech stack

| Layer | Technology |
|-------|------------|
| **Foundation model** | Amazon Bedrock (DeepSeek) — requirements extraction, image review, call summaries, rankings, PDF report content |
| **Car search** | AWS Nova Act — browser automation to cars.com and Facebook Marketplace; results scrubbed and parsed |
| **Voice (dealer calls)** | Amazon Nova Sonic — real-time voice agent for outbound dealer calls; Twilio for telephony |
| **Calls and SMS** | Twilio — outbound calls and messaging |
| **Backend** | Python, FastAPI, WebSockets |
| **Frontend** | React (Vite), TypeScript |
| **Database** | MongoDB (Motor + Beanie ODM) |

---

## Run locally

### Prerequisites

- **Python 3** (virtual env recommended)
- **Node.js** and **npm**
- **MongoDB** — Docker for local, or your own deployment

### 1. Get API keys and config

Copy `backend/.env.example` to `backend/.env` and fill in the values. You will need AWS credentials (for Bedrock, Nova Act, and Nova Sonic), Twilio keys, and optionally Deepgram (fallback voice) and Foxit (PDF services).

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
Set `MONGODB_URL` in `backend/.env` to your deployment.

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
| GET | `/api/sessions/{session_id}/export-pdf` | Export dashboard PDF |
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

In `backend/.env` (see `backend/.env.example` for full list):

- **AWS / Bedrock (DeepSeek)** — `BEDROCK_CHAT_MODEL_ID`, `BEDROCK_REGION`; use `ACCESS_KEY` / `SECRET_ACCRESS_KEY` or `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`
- **Nova Act (car search)** — Set `CAR_SEARCH_PROVIDER=nova_act`. For real listings from cars.com and Facebook Marketplace, configure `NOVA_ACT_WORKFLOW_NAME`, `NOVA_ACT_RESULT_S3_BUCKET`, and `NOVA_ACT_RESULT_S3_PREFIX` after deploying the workflow. Without the workflow, the backend uses Bedrock-only synthetic listings.
- **Nova Sonic (voice)** — Uses the same AWS credentials; optional `NOVA_SONIC_MODEL_ID`, `NOVA_SONIC_REGION`
- **Twilio** — `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`
- **Deepgram** — `DEEPGRAM_API_KEY` (optional fallback when Nova Sonic is not configured)
- **Server** — `SERVER_BASE_URL` (public backend URL for Twilio webhooks; e.g. ngrok for local)
- **MongoDB** — `MONGODB_URL` (optional; default/local uses Docker)
- **Foxit** — `FOXIT_CLIENT_ID`, `FOXIT_CLIENT_SECRET`, `FOXIT_API_HOST` (optional; PDF generation)
- **MarketCheck** — `CAR_SEARCH_PROVIDER=marketcheck` and `MARKETCHECK_API_KEY` (optional fallback when Nova Act returns no results)
