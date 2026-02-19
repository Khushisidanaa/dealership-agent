# Dealership Agent – run FastAPI and dependencies
# For local API testing: make mongo-local then make run (Mongo on localhost:27017)

PYTHON ?= python3
VENV ?= .venv
BACKEND = backend
PORT ?= 8000
CERTS_DIR = .certs

.PHONY: install run run-http run-https mongo mongo-local stop help

help:
	@echo "  make mongo-local  Start MongoDB on localhost:27017 (for make run)"
	@echo "  make mongo       Start MongoDB via docker compose (no host port)"
	@echo "  make run         Start FastAPI over HTTP (port $(PORT))"
	@echo "  make run-https   Start FastAPI over HTTPS (self-signed cert)"
	@echo "  make install     Install backend deps"
	@echo "  make stop        Stop Docker stack"

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
