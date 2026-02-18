# Deploying the Dealership Agent Backend on Linode

This guide walks you through deploying the full backend (FastAPI + MongoDB) on a Linode instance using Docker Compose. The stack is sized for a 1GB or 2GB Linode plan.

---

## Prerequisites

- A [Linode](https://www.linode.com/) account (Akamai hackathon: “Build the Most Creative Open-Source Solution on Linode”).
- Your repo pushed to GitHub (or another Git host) so you can clone it on the server.
- Optional: a domain name pointed at your Linode IP (for a custom URL or later HTTPS).

---

## 1. Create a Linode Instance

1. In the [Linode Cloud Manager](https://cloud.linode.com/), click **Create Linode**.
2. **Image:** Choose **Ubuntu 24.04 LTS** (or another supported Ubuntu/Debian release).
3. **Region:** Pick one close to your users.
4. **Plan:** **Shared CPU – 1 GB** or **2 GB** is enough for the backend + MongoDB (compose limits are set to 512MB per service).
5. Set root password and optionally add an SSH key.
6. Create the Linode and wait for it to boot. Note the **IP address**.

---

## 2. Connect and Harden the Server (Optional but Recommended)

```bash
ssh root@YOUR_LINODE_IP
```

- Update the system: `apt update && apt upgrade -y`
- Create a non-root user (e.g. `adduser deploy` and add to `sudo` / `docker`).
- For production, disable root SSH and use key-based auth.

---

## 3. Install Docker and Docker Compose

On Ubuntu (as root or with sudo):

```bash
# Install Docker
curl -fsSL https://get.docker.com | sh

# Add your user to the docker group (if not root)
usermod -aG docker $USER
# Log out and back in for the group to apply

# Verify
docker --version
docker compose version
```

You need **Docker Compose V2** (`docker compose`, not `docker-compose`). The script above installs it as a Docker plugin.

---

## 4. Get the Code on the Server

From your home or project directory:

```bash
# Clone (replace with your repo URL)
git clone https://github.com/YOUR_ORG/dealership-agent.git
cd dealership-agent
```

Or upload the project via `scp` / `rsync` if you’re not using Git.

---

## 5. Configure Environment (Optional)

The app runs with defaults from `docker-compose.yml` for MongoDB (`MONGO_URI`, `MONGO_DB_NAME`). For API keys and other settings:

1. In the repo root (same directory as `docker-compose.yml`), create a `.env` file:

   ```bash
   cp .env.example .env
   nano .env
   ```

2. Set any variables your app needs (see `backend/app/config.py`). Examples:

   - `OPENAI_API_KEY=...`
   - `TWILIO_ACCOUNT_SID=...`, `TWILIO_AUTH_TOKEN=...`, `TWILIO_PHONE_NUMBER=...`
   - `DEEPGRAM_API_KEY=...`
   - `SERVER_BASE_URL=http://YOUR_LINODE_IP:8000` (or your domain later)

Compose does not need to pass `MONGO_URI` or `MONGO_DB_NAME` again unless you override them (e.g. for an external MongoDB). For the default stack, the values in `docker-compose.yml` are enough.

---

## 6. Build and Run

From the **repository root** (where `docker-compose.yml` and `Dockerfile` live):

```bash
docker compose build
docker compose up -d
```

Check that both containers are up:

```bash
docker compose ps
```

You should see `dealership-backend` and `dealership-mongo` running. Backend is on port **8000**, MongoDB is only on the internal network.

---

## 7. Open the Firewall (If Enabled)

If you use **UFW**:

```bash
ufw allow 22/tcp   # SSH
ufw allow 8000/tcp # Backend API
ufw enable
ufw status
```

Replace `22` with your SSH port if you changed it.

---

## 8. Verify the Deployment

- **Health check:**  
  `http://YOUR_LINODE_IP:8000/health`  
  Expected: `{"status":"ok"}`

- **API root:**  
  `http://YOUR_LINODE_IP:8000/`  
  Expected: `{"service":"dealership-agent"}` (or similar from your app)

- **Logs:**

  ```bash
  docker compose logs -f backend
  docker compose logs -f mongo
  ```

---

## 9. Persistence and Restarts

- **Data:** MongoDB data is stored in a Docker volume `mongo_data`. It survives `docker compose down` and reboots.
- **Restart policy:** Both services use `restart: unless-stopped`, so they come back after a Linode reboot.

To restart only the app:

```bash
docker compose restart backend
```

---

## 10. Updating the App

After pulling new code or changing config:

```bash
cd dealership-agent
git pull   # if using Git
docker compose build backend
docker compose up -d
```

MongoDB data is unchanged as long as you don’t remove the `mongo_data` volume.

---

## 11. Optional: Custom Domain and HTTPS

- In your DNS provider, add an **A record** for your domain (e.g. `api.yourdomain.com`) pointing to your Linode IP.
- On the Linode, put a reverse proxy (e.g. **Caddy** or **Nginx**) in front of the backend and terminate TLS there. The backend can keep listening on `localhost:8000`; the proxy listens on 80/443 and forwards to `http://127.0.0.1:8000`.
- Set `SERVER_BASE_URL=https://api.yourdomain.com` (and any CORS origins) in `.env` or in the app config.

---

## Quick Reference

| Item            | Value                          |
|-----------------|--------------------------------|
| Backend URL     | `http://YOUR_LINODE_IP:8000`   |
| Health endpoint | `GET /health`                  |
| Compose project | Run from repo root             |
| MongoDB         | Internal only (`mongo:27017`)  |
| Memory          | 512MB limit per service (tunable in `docker-compose.yml`) |

For issues, check `docker compose logs` and that `MONGO_URI` / `MONGO_DB_NAME` in the compose file match what the backend expects (they are set correctly in the repo for this stack).
