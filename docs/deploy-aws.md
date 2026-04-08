# Deploy on AWS (EC2)

Deploy the Dealership Agent on an **Amazon EC2 Linux instance**. The flow is the same as [deploy-linode.md](deploy-linode.md): one VM runs the React UI (built and served by the FastAPI backend) and the API. The app binds to `0.0.0.0` so it is reachable from the internet.

---

## 1. Launch an EC2 instance

### 1.1 In the AWS Console

1. **EC2** → **Launch instance**.
2. **Name:** e.g. `dealership-agent`.
3. **AMI:** **Ubuntu Server 22.04 LTS** (or Amazon Linux 2023).
4. **Instance type:** e.g. `t3.small` (2 vCPU, 2 GiB). Use `t3.micro` for light use; scale up if you run MongoDB on the same instance.
5. **Key pair:** Create or select an SSH key; download the `.pem` and `chmod 600` it.
6. **Network / Security group:**
   - Create or use a security group that allows:
     - **SSH:** port **22** from your IP (or `0.0.0.0/0` only if you accept the risk).
     - **App:** port **8000** from `0.0.0.0/0` (so users and Twilio can reach the backend).
   - If you put the app behind HTTPS later (ALB or nginx), you can restrict 8000 to the load balancer or localhost.
7. **Storage:** 20–30 GB is usually enough.
8. Launch the instance.

### 1.2 Optional: Elastic IP

- **EC2** → **Elastic IPs** → **Allocate** → **Associate** with your instance.
- Use this IP in `SERVER_BASE_URL` and to open the app so the URL doesn’t change after restarts.

---

## 2. SSH and one-time setup on the VM

### 2.1 Connect

```bash
ssh -i /path/to/your-key.pem ubuntu@<ec2-public-ip>
```

(Use `ec2-user` for Amazon Linux.)

### 2.2 Install dependencies

**Node.js 20** (for building the UI):

```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs
```

**Python 3.10+** and **pip** (Ubuntu):

```bash
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-venv
```

**MongoDB** (optional if you use Atlas):

- **Option A — MongoDB on EC2:**  
  [Install MongoDB Community on Ubuntu](https://www.mongodb.com/docs/manual/tutorial/install-mongodb-on-ubuntu/) then use `MONGODB_URI=mongodb://localhost:27017`.
- **Option B — Atlas:**  
  Create a cluster, get the connection string, and set `MONGODB_URI=mongodb+srv://...` in `backend/.env`. No MongoDB install on the VM.

---

## 3. Clone repo and configure env

```bash
sudo mkdir -p /opt && sudo chown "$USER" /opt
cd /opt
git clone <your-repo-url> dealership-agent
cd dealership-agent
```

Create `backend/.env` (copy from `backend/.env.example` and fill in):

```bash
cp backend/.env.example backend/.env
# Edit backend/.env (nano or vim)
```

Set at least:

```bash
# MongoDB: local or Atlas
MONGODB_URI=mongodb://localhost:27017
# or MONGODB_URI=mongodb+srv://user:pass@cluster....mongodb.net/...
MONGODB_DB_NAME=dealership_agent

# Backend URL Twilio and webhooks use — use your EC2 public IP or domain (no shorteners)
SERVER_BASE_URL=http://YOUR_EC2_PUBLIC_IP:8000

# API keys (OpenAI, Twilio, Deepgram, etc. — see .env.example)
OPENAI_API_KEY=sk-...
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
TWILIO_PHONE_NUMBER=+1...
# DEEPGRAM_API_KEY=...  # if not using Nova Sonic
```

For **voice/WebSocket**, `SERVER_BASE_URL` must be the **direct** URL (e.g. `http://<ec2-ip>:8000`). Do **not** use a shortener (TinyURL, etc.); Twilio needs a direct WebSocket handshake.

**AWS (Bedrock / Nova Act):** If the app uses Bedrock or Nova Act, configure credentials on the instance (e.g. IAM role for the EC2 instance, or `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` in `.env`). Prefer IAM roles so you don’t store long‑lived keys in `.env`.

---

## 4. Python venv and deploy

```bash
cd /opt/dealership-agent
python3 -m venv .venv
source .venv/bin/activate
make deploy
```

This runs `make install` (backend pip deps) and `make build-ui` (npm ci + build). Then:

```bash
make deploy-run
```

The app listens on **port 8000** bound to **0.0.0.0**. Open:

- **http://&lt;ec2-public-ip&gt;:8000** — UI and API

To keep it running after you close SSH, use **tmux**/ **screen** or **systemd** (below).

---

## 5. Firewall (security group)

In AWS, opening **8000** is done in the **security group** (step 1). On the VM you can still use `ufw`:

```bash
sudo ufw allow 22/tcp
sudo ufw allow 8000/tcp
sudo ufw enable
```

---

## 6. Run as a systemd service (recommended)

Create `/etc/systemd/system/dealership-agent.service` (adjust paths if you use a different install dir):

```ini
[Unit]
Description=Dealership Agent
After=network.target
# If MongoDB runs on this host:
# After=network.target mongod.service

[Service]
Type=simple
User=ubuntu
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

Use `User=ec2-user` and paths under `/home/ec2-user` if you installed there on Amazon Linux.

---

## 7. Different port (e.g. 80)

To use port 80 (requires root or capabilities):

```bash
make deploy-run DEPLOY_PORT=80
```

Or in the systemd unit, set `--port 80` and run the service as root (or use `setcap` / a reverse proxy).

---

## 8. HTTPS (optional)

- **Option A — Application Load Balancer (ALB) + ACM**
  - Create an ALB in the same VPC, add an HTTPS listener with a certificate from **AWS Certificate Manager (ACM)**.
  - Target group: EC2 instance, port 8000 (or 80).
  - Point your domain to the ALB. Set `SERVER_BASE_URL=https://your-domain`.
- **Option B — nginx + Let’s Encrypt on the same EC2**
  - Install nginx and Certbot, proxy `https://your-domain` → `http://127.0.0.1:8000`, and set `SERVER_BASE_URL=https://your-domain`.

---

## 9. Summary checklist

| Step | Action |
|------|--------|
| 1 | Launch EC2 (Ubuntu/AL2023), security group: 22, 8000 |
| 2 | (Optional) Allocate and associate an Elastic IP |
| 3 | SSH, install Node 20, Python 3, MongoDB or use Atlas |
| 4 | Clone repo, create `backend/.env`, set `SERVER_BASE_URL=http://<ec2-ip>:8000` |
| 5 | `python3 -m venv .venv && source .venv/bin/activate` |
| 6 | `make deploy` then `make deploy-run` (or use systemd) |
| 7 | Open http://&lt;ec2-ip&gt;:8000 |

Deployment on AWS EC2 is the same as on a Linode Linux VM: install stack → clone → env → build → run (and optionally systemd + HTTPS).
