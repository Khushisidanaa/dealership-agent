from fastapi import APIRouter

from app.api.sessions import get_session_or_404
from app.models.schemas import PreferencesRequest, PreferencesResponse

router = APIRouter(prefix="/api/sessions/{session_id}/preferences", tags=["preferences"])


@router.post("", response_model=PreferencesResponse)
async def submit_preferences(session_id: str, body: PreferencesRequest):
    """Save static questionnaire preferences for a session."""
    session = await get_session_or_404(session_id)

    session.preferences = body.model_dump()
    session.status = "preferences_set"
    await session.save()

    return PreferencesResponse(
        session_id=session.session_id,
        preferences_saved=True,
        next_step="chat",
    )
