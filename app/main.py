"""
Minimal FastAPI app for deployment. Add your routes and DB usage here.
"""
from fastapi import FastAPI

app = FastAPI(title="Dealership Agent", version="0.1.0")


@app.get("/health")
def health():
    """Health check for Linode/orchestrator."""
    return {"status": "ok"}


@app.get("/")
def root():
    return {"service": "dealership-agent"}
