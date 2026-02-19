"""
CRUD for user requirements: create, edit, delete, and get by user_id.
Storage is keyed by user_id (one requirements doc per user).
"""

from typing import Any, Optional

from app.models.documents import UserRequirementsDocument, utc_now
from app.models.schemas import UserRequirements


def merge_filters_into_requirements(
    current: UserRequirements,
    updated_filters: dict[str, Any],
) -> UserRequirements:
    """
    Merge LLM updated_filters (flat dict) into current UserRequirements.
    Only updates keys that exist on UserRequirements; coerces types for lists/enums.
    """
    if not updated_filters:
        return current
    data = current.model_dump()
    for key, value in updated_filters.items():
        if key not in data:
            continue
        if value is None:
            continue
        if isinstance(data[key], list):
            if isinstance(value, list):
                data[key] = value
            elif isinstance(value, str):
                data[key] = [x.strip() for x in value.split(",") if x.strip()]
            else:
                data[key] = [value]
        elif isinstance(data[key], int) and isinstance(value, (float, str)):
            try:
                data[key] = int(value)
            except (TypeError, ValueError):
                pass
        elif isinstance(data[key], float) and isinstance(value, str):
            try:
                data[key] = float(value)
            except (TypeError, ValueError):
                pass
        else:
            data[key] = value
    return UserRequirements.model_validate(data)


async def create_user_requirements(user_id: str, requirements: UserRequirements) -> UserRequirements:
    """
    Create a new user-requirements document for the given user_id.
    Fails if one already exists for this user_id; use update_user_requirements to overwrite.
    """
    existing = await UserRequirementsDocument.find_one(
        UserRequirementsDocument.user_id == user_id
    )
    if existing:
        raise ValueError(f"User requirements already exist for user_id={user_id}; use update instead")
    doc = UserRequirementsDocument(
        user_id=user_id,
        requirements=requirements.model_dump(),
    )
    await doc.insert()
    return UserRequirements.model_validate(doc.requirements)


async def get_user_requirements(user_id: str) -> Optional[UserRequirements]:
    """
    Get requirements for a user by user_id. Returns None if not found.
    """
    doc = await UserRequirementsDocument.find_one(
        UserRequirementsDocument.user_id == user_id
    )
    if not doc:
        return None
    return UserRequirements.model_validate(doc.requirements)


async def update_user_requirements(user_id: str, requirements: UserRequirements) -> Optional[UserRequirements]:
    """
    Update requirements for the given user_id. Creates the document if it does not exist (upsert).
    Returns the saved requirements.
    """
    doc = await UserRequirementsDocument.find_one(
        UserRequirementsDocument.user_id == user_id
    )
    data = requirements.model_dump()
    if doc:
        doc.requirements = data
        doc.updated_at = utc_now()
        await doc.save()
    else:
        doc = UserRequirementsDocument(user_id=user_id, requirements=data)
        await doc.insert()
    return UserRequirements.model_validate(doc.requirements)


async def delete_user_requirements(user_id: str) -> bool:
    """
    Delete the user-requirements document for the given user_id.
    Returns True if a document was deleted, False if none existed.
    """
    doc = await UserRequirementsDocument.find_one(
        UserRequirementsDocument.user_id == user_id
    )
    if not doc:
        return False
    await doc.delete()
    return True
