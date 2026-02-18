# ---- Build stage: install dependencies only ----
FROM python:3.12-slim as builder

WORKDIR /build

# Install deps in a virtual env for a smaller final image
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY backend/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ---- Runtime stage: minimal image for Linode ----
FROM python:3.12-slim as runtime

# Security: non-root user (Linode / production best practice)
RUN groupadd --gid 1000 app && \
    useradd --uid 1000 --gid app --shell /bin/bash --create-home app

WORKDIR /app

# Copy only the virtual env from builder (no build tools in runtime)
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Application code (backend app lives in /app: app/, config.py, main.py, etc.)
COPY --chown=app:app backend/ .

USER app

# Single exposed port for the API (no Mongo exposed to host in production)
EXPOSE 8000

# Healthcheck so Linode/orchestrator can detect unhealthy containers
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')" || exit 1

# Run the app (override with docker run or compose if needed)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
