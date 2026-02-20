from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.models.database import init_db, close_db, get_db_handler

# Project root (backend/app/main.py -> backend -> root)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
UI_DIST = PROJECT_ROOT / "ui" / "dist"
from app.api import (
    auth,
    sessions,
    preferences,
    chat,
    search,
    listings,
    dashboard,
    test_drive,
    users,
    voice,
    analyze,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    app.state.db = get_db_handler()
    yield
    await close_db()


app = FastAPI(
    title="Dealership Agent API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(sessions.router)
app.include_router(preferences.router)
app.include_router(chat.router)
app.include_router(search.router)
app.include_router(listings.router)
app.include_router(dashboard.router)
app.include_router(test_drive.router)
app.include_router(users.router)
app.include_router(voice.router)
app.include_router(analyze.router)


@app.get("/health")
async def health_check():
    return {"status": "ok"}


# Serve built UI (e.g. after make build-ui) so one server serves both API and frontend
if UI_DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(UI_DIST), html=True), name="ui")
