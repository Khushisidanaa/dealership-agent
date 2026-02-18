"""
MongoDB driver: connection lifecycle, raw client/database access, and index-backed queries.
Use Beanie Document.find_one() / find() for typed queries; use get_db() for raw key search.

At startup: await init_db() then db_handler = get_db_handler(). Pass db_handler around
or use app.state.db = get_db_handler() and use request.app.state.db in routes.
"""
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from beanie import init_beanie

from app.config import get_settings
from app.models.documents import ALL_DOCUMENT_MODELS
from app.models.db_handler import DBHandler

_client: AsyncIOMotorClient | None = None
_db_handler: DBHandler | None = None


async def init_db() -> None:
    """Initialize MongoDB connection, Beanie ODM, indexes, and the DB handler."""
    global _client, _db_handler
    settings = get_settings()
    _client = AsyncIOMotorClient(settings.mongodb_url)
    db = _client[settings.mongodb_db_name]
    await init_beanie(database=db, document_models=ALL_DOCUMENT_MODELS)
    _db_handler = DBHandler()


def get_client() -> AsyncIOMotorClient:
    """Return the Motor client. Use for low-level access (e.g. custom aggregations)."""
    if _client is None:
        raise RuntimeError("DB not initialized; call init_db() first (e.g. in app lifespan).")
    return _client


def get_db() -> AsyncIOMotorDatabase:
    """Return the Motor database. Use for key-based search on raw collections."""
    settings = get_settings()
    return get_client()[settings.mongodb_db_name]


def get_db_handler() -> DBHandler:
    """Return the DB handler (create at startup via init_db()). Use for insert/get/update/delete by model type."""
    if _db_handler is None:
        raise RuntimeError("DB not initialized; call init_db() first (e.g. in app lifespan).")
    return _db_handler


async def find_one_by_keys(collection_name: str, **keys: Any) -> dict | None:
    """
    Search a collection by key-value pairs (index-friendly when keys are indexed).
    Returns the first matching document or None.
    """
    coll = get_db()[collection_name]
    return await coll.find_one(keys)


async def find_many_by_keys(
    collection_name: str,
    *,
    limit: int = 100,
    sort: list[tuple[str, int]] | None = None,
    **keys: Any,
) -> list[dict]:
    """
    Search a collection by key-value pairs. Optional sort e.g. [("created_at", -1)].
    """
    coll = get_db()[collection_name]
    cursor = coll.find(keys)
    if sort:
        cursor = cursor.sort(sort)
    cursor = cursor.limit(limit)
    return await cursor.to_list(length=limit)


async def close_db() -> None:
    """Close MongoDB connection."""
    global _client, _db_handler
    if _client is not None:
        _client.close()
        _client = None
    _db_handler = None


# ---------------------------------------------------------------------------
# Example usage (commented)
# ---------------------------------------------------------------------------
# Set up at startup (e.g. FastAPI lifespan):
#   await init_db()
#   db = get_db_handler()   # then e.g. app.state.db = db
#
# Add a new user requirement:
#   from app.models import get_db_handler
#   from app.models.schemas import UserRequirements
#   db = get_db_handler()
#   req = UserRequirements(price_max=35_000, zip_code="90210", brand_preference=["Toyota"])
#   await db.insert(UserRequirements, user_id="user_123", data=req)
#
# Get / update / delete user requirements:
#   saved = await db.get(UserRequirements, user_id="user_123")
#   await db.update(UserRequirements, user_id="user_123", data=req)
#   await db.delete(UserRequirements, user_id="user_123")
#
# Add a new dealer contact:
#   from app.models.schemas import DealershipContact, DealershipContactStatus
#   contact = DealershipContact(user_id="user_123", dealer_id="dealer_456", dealership_name="Acme Cars", address="123 Main St", distance_miles=5.2, status=DealershipContactStatus.TEXT, cars=[])
#   await db.insert(DealershipContact, user_id="user_123", dealer_id="dealer_456", data=contact)
#
# List all dealers for a user:
#   contacts = await db.find(DealershipContact, user_id="user_123")
