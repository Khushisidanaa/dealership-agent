from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.models.documents import (
    UserDocument,
    SessionDocument,
    ChatMessageDocument,
    SearchResultDocument,
    CommunicationDocument,
    ShortlistDocument,
)
from app.models.schemas import SessionResponse

router = APIRouter(prefix="/api", tags=["sessions"])


class CreateSessionRequest(BaseModel):
    user_id: Optional[str] = None


@router.post("/sessions", response_model=SessionResponse, status_code=201)
async def create_session(body: Optional[CreateSessionRequest] = None):
    """Create a session, optionally linked to an existing authenticated user."""
    uid = body.user_id if body else None

    if uid:
        existing = await UserDocument.find_one(UserDocument.user_id == uid)
        if not existing:
            raise HTTPException(status_code=404, detail="User not found")
    else:
        user = UserDocument()
        await user.insert()
        uid = user.user_id

    session = SessionDocument(user_id=uid)
    await session.insert()
    return SessionResponse(
        session_id=session.session_id,
        user_id=session.user_id,
        created_at=session.created_at,
    )


@router.get("/users/{user_id}/sessions")
async def list_user_sessions(user_id: str):
    """Return all sessions for a user, newest first, with summary info."""
    sessions = (
        await SessionDocument.find(SessionDocument.user_id == user_id)
        .sort("-created_at")
        .limit(20)
        .to_list()
    )

    results = []
    for s in sessions:
        prefs = s.preferences or {}
        label_parts = []
        if prefs.get("make"):
            label_parts.append(prefs["make"])
        if prefs.get("model"):
            label_parts.append(prefs["model"])
        if prefs.get("price_max"):
            label_parts.append(f"${prefs['price_max']:,.0f} budget")
        label = ", ".join(label_parts) if label_parts else "New search"

        search_doc = await SearchResultDocument.find_one(
            SearchResultDocument.session_id == s.session_id,
            SearchResultDocument.status == "completed",
        )
        vehicle_count = len(search_doc.vehicles) if search_doc else 0

        comm_doc = await CommunicationDocument.find_one(
            CommunicationDocument.session_id == s.session_id
        )
        has_calls = comm_doc is not None

        results.append({
            "session_id": s.session_id,
            "created_at": s.created_at.isoformat(),
            "phase": s.phase,
            "label": label,
            "vehicle_count": vehicle_count,
            "has_calls": has_calls,
        })

    return {"sessions": results}


@router.get("/sessions/{session_id}/state")
async def get_session_state(session_id: str):
    """Return a snapshot of session progress for resuming."""
    session = await get_session_or_404(session_id)

    search_doc = await SearchResultDocument.find_one(
        SearchResultDocument.session_id == session_id,
        SearchResultDocument.status == "completed",
    )
    has_search = search_doc is not None
    vehicle_count = len(search_doc.vehicles) if search_doc else 0

    comms = await CommunicationDocument.find(
        CommunicationDocument.session_id == session_id
    ).to_list()
    has_calls = len(comms) > 0

    has_shortlist = await ShortlistDocument.find_one(
        ShortlistDocument.session_id == session_id
    ) is not None

    chat_count = await ChatMessageDocument.find(
        ChatMessageDocument.session_id == session_id
    ).count()

    return {
        "session_id": session_id,
        "phase": session.phase,
        "preferences": session.preferences,
        "has_search_results": has_search,
        "has_calls": has_calls,
        "has_dashboard": has_shortlist or has_calls,
        "vehicle_count": vehicle_count,
        "chat_message_count": chat_count,
    }


async def get_session_or_404(session_id: str) -> SessionDocument:
    """Shared helper to fetch a session or raise 404."""
    session = await SessionDocument.find_one(
        SessionDocument.session_id == session_id
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session
