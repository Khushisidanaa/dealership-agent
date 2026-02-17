from fastapi import APIRouter, HTTPException

from app.models.documents import SessionDocument
from app.models.schemas import SessionResponse

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.post("", response_model=SessionResponse, status_code=201)
async def create_session():
    """Create a new search session."""
    session = SessionDocument()
    await session.insert()
    return SessionResponse(
        session_id=session.session_id,
        created_at=session.created_at,
    )


async def get_session_or_404(session_id: str) -> SessionDocument:
    """Shared helper to fetch a session or raise 404."""
    session = await SessionDocument.find_one(
        SessionDocument.session_id == session_id
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session
