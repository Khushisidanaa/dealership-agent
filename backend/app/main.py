from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.models.database import init_db, close_db, get_db_handler
from app.api import (
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
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
