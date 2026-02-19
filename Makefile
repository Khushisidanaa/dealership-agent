# Dealership Agent – run FastAPI and dependencies
# For local API testing: make mongo-local then make run (Mongo on localhost:27017)
# Deploy on Linode: make deploy (builds UI + runs backend on 0.0.0.0 for public access)

PYTHON ?= python3
VENV ?= .venv
BACKEND = backend
UI = ui
PORT ?= 5000
DEPLOY_PORT ?= 8000
CERTS_DIR = .certs
NODE ?= node
NPM ?= npm

.PHONY: install run run-http run-https mongo mongo-local stop help build-ui deploy deploy-run

help:
	@echo "  make mongo-local  Start MongoDB on localhost:27017 (for make run)"
	@echo "  make mongo       Start MongoDB via docker compose (no host port)"
	@echo "  make run         Start FastAPI over HTTP (port $(PORT))"
	@echo "  make run-https   Start FastAPI over HTTPS (self-signed cert)"
	@echo "  make install     Install backend deps"
	@echo "  make stop        Stop Docker stack"
	@echo "  make build-ui    Build React UI into ui/dist (for deploy)"
	@echo "  make deploy      Build UI + install backend deps (run deploy-run after)"
	@echo "  make deploy-run  Run app on 0.0.0.0:$(DEPLOY_PORT) (public); run after make deploy"

# Use public PyPI so install works even if pip is pointed at a custom index (e.g. Artifactory)
install:
	$(PYTHON) -m pip install --index-url https://pypi.org/simple/ -r $(BACKEND)/requirements.txt

# MongoDB for full stack (backend in Docker): no host port
mongo:
	docker compose up -d mongo
	@echo "Mongo running (internal). Use docker compose up to run backend too."

# MongoDB for local API testing: publish 27017 so make run can connect
mongo-local:
	@docker run -d -p 27017:27017 --name dealership-mongo-local mongo:7 2>/dev/null || true
	@echo "Mongo on localhost:27017. Run: make run"

# Run FastAPI over HTTP (needs Mongo on localhost:27017 — run make mongo-local first)
run: run-http
run-http:
	@echo "Starting FastAPI at http://127.0.0.1:$(PORT)"
	@echo "Docs: http://127.0.0.1:$(PORT)/docs"
	cd $(BACKEND) && $(PYTHON) -m uvicorn app.main:app --reload --host 127.0.0.1 --port $(PORT)

# Run FastAPI over HTTPS (self-signed cert in .certs/)
run-https: $(CERTS_DIR)/key.pem $(CERTS_DIR)/cert.pem
	@echo "Starting FastAPI at https://127.0.0.1:$(PORT)"
	cd $(BACKEND) && $(PYTHON) -m uvicorn app.main:app --reload --host 127.0.0.1 --port $(PORT) --ssl-keyfile=../$(CERTS_DIR)/key.pem --ssl-certfile=../$(CERTS_DIR)/cert.pem

$(CERTS_DIR)/key.pem $(CERTS_DIR)/cert.pem:
	@mkdir -p $(CERTS_DIR)
	openssl req -x509 -newkey rsa:4096 -keyout $(CERTS_DIR)/key.pem -out $(CERTS_DIR)/cert.pem -days 365 -nodes -subj "/CN=localhost"
	@echo "Created self-signed cert in $(CERTS_DIR)/"

stop:
	docker compose down

# --- Linode / production deploy ---

build-ui:
	@echo "Building UI..."
	cd $(UI) && $(NPM) ci && $(NPM) run build
	@echo "UI built at $(UI)/dist"

# Prepare for deploy: install backend deps and build UI. Run once on the server.
deploy: install build-ui
	@echo "Deploy ready. Run: make deploy-run"
	@echo "Then open http://<this-machine-ip>:$(DEPLOY_PORT)"

# Run the app bound to 0.0.0.0 so it is reachable from the public internet.
# Run this on the Linode VM (after make deploy). Use tmux/screen or systemd to keep it running.
deploy-run:
	@echo "Starting app on http://0.0.0.0:$(DEPLOY_PORT) (public)"
	@echo "Press Ctrl+C to stop."
	cd $(BACKEND) && $(PYTHON) -m uvicorn app.main:app --host 0.0.0.0 --port $(DEPLOY_PORT)
