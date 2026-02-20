# Deploy on Linode

One server runs both the React UI and the FastAPI backend. The app listens on `0.0.0.0` so it is reachable from the public internet.

## 1. On your Linode VM (after SSH)

### Install dependencies (once)

- **Node.js 18+** (for building the UI):  
  `curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash - && sudo apt-get install -y nodejs`
- **Python 3.9+** and **pip**
- **MongoDB** (e.g. install locally or use a managed MongoDB; set `MONGODB_URL` in `.env`)

### Clone repo and env

```bash
cd /opt   # or your preferred directory
sudo git clone <your-repo-url> dealership-agent
cd dealership-agent
```

Create `backend/.env` with at least:

```bash
MONGODB_URL=mongodb://localhost:27017
MONGODB_DB_NAME=dealership_agent
OPENAI_API_KEY=sk-...
# Required for voice (Twilio + WebSocket): use your Linode's direct URL — do NOT use a URL shortener (TinyURL, etc.)
SERVER_BASE_URL=http://YOUR_LINODE_PUBLIC_IP:8000
# Optional: MARKETCHECK_API_KEY=... for listings
```

**Important for voice/WebSocket:** `SERVER_BASE_URL` must be the **direct** URL Twilio can reach (e.g. `http://<linode-ip>:8000`). Do **not** set it to a TinyURL or other shortener. Shorteners return HTTP redirects (301/302); Twilio’s Media Stream needs a WebSocket handshake (HTTP 101). Use a short URL only for opening the app in a browser; the backend must use the real base URL.

### Python venv (recommended)

```bash
python3 -m venv .venv
source .venv/bin/activate
```

## 2. Deploy and run

```bash
make deploy
```

This runs `make install` (backend pip deps) and `make build-ui` (npm ci + build). Then:

```bash
make deploy-run
```

This starts the app on **port 8000** bound to **0.0.0.0**. Open:

- **http://&lt;your-linode-public-ip&gt;:8000** — UI and API

To keep it running after you close SSH, use **tmux** or **systemd** (see below).

## 3. Firewall

Allow port 8000 (or your chosen port):

```bash
sudo ufw allow 8000/tcp
sudo ufw enable
```

## 4. Run as a systemd service (optional)

Create `/etc/systemd/system/dealership-agent.service` (adjust paths if you cloned elsewhere):

```ini
[Unit]
Description=Dealership Agent
After=network.target mongodb.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/dealership-agent/backend
Environment="PATH=/opt/dealership-agent/.venv/bin"
ExecStart=/opt/dealership-agent/.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable dealership-agent
sudo systemctl start dealership-agent
sudo systemctl status dealership-agent
```

## 5. Change port

To use port 80 (requires root) or another port:

```bash
make deploy-run DEPLOY_PORT=80
```

Or set `DEPLOY_PORT` in the Makefile or in the systemd `ExecStart` line.
