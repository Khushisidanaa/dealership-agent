from contextlib import asynccontextmanager
from collections import defaultdict

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.models.database import init_db, close_db, get_db_handler
from app.api import (
    sessions,
    preferences,
    chat,
    search,
    listings,
    dashboard,
    communication,
    test_drive,
    documents,
    voice,
)


# ---------------------------------------------------------------------------
# WebSocket connection manager
# ---------------------------------------------------------------------------


class ConnectionManager:
    """Manages active WebSocket connections per session."""

    def __init__(self):
        self.active: dict[str, list[WebSocket]] = defaultdict(list)

    async def connect(self, session_id: str, ws: WebSocket):
        await ws.accept()
        self.active[session_id].append(ws)

    def disconnect(self, session_id: str, ws: WebSocket):
        self.active[session_id].remove(ws)
        if not self.active[session_id]:
            del self.active[session_id]

    async def broadcast(self, session_id: str, message: dict):
        for ws in self.active.get(session_id, []):
            await ws.send_json(message)


ws_manager = ConnectionManager()


# ---------------------------------------------------------------------------
# App lifecycle
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    app.state.db = get_db_handler()
    yield
    await close_db()


# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Dealership Agent API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Register routers
# ---------------------------------------------------------------------------

app.include_router(sessions.router)
app.include_router(preferences.router)
app.include_router(chat.router)
app.include_router(search.router)
app.include_router(listings.router)
app.include_router(dashboard.router)
app.include_router(communication.router)
app.include_router(test_drive.router)
app.include_router(documents.router)
app.include_router(voice.router)


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------


@app.websocket("/ws/sessions/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await ws_manager.connect(session_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Client can send pings or commands; for now just keep alive
    except WebSocketDisconnect:
        ws_manager.disconnect(session_id, websocket)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@app.get("/health")
async def health_check():
    return {"status": "ok"}
