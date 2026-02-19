"""
User requirements: persist full requirements by user_id (e.g. from session).
Used when the UI saves requirements from the requirements modal ("Mark complete").
"""
from fastapi import APIRouter, Request

from app.models.schemas import UserRequirements

router = APIRouter(prefix="/api/users", tags=["users"])


def _get_db(request: Request):
    return request.app.state.db


@router.put("/{user_id}/requirements", response_model=UserRequirements)
async def update_user_requirements(user_id: str, request: Request, data: UserRequirements):
    """Upsert requirements for a user. Called when user marks requirements complete in the UI."""
    db = _get_db(request)
    return await db.update(UserRequirements, user_id=user_id, data=data)
