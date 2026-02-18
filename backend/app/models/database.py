"""
MongoDB driver: connection lifecycle, raw client/database access, and index-backed queries.
Use Beanie Document.find_one() / find() for typed queries; use get_db() for raw key search.
"""
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from beanie import init_beanie

from app.config import get_settings
from app.models.documents import ALL_DOCUMENT_MODELS

_client: AsyncIOMotorClient | None = None


async def init_db() -> None:
    """Initialize MongoDB connection, Beanie ODM, and ensure indexes."""
    global _client
    settings = get_settings()
    _client = AsyncIOMotorClient(settings.mongodb_url)
    db = _client[settings.mongodb_db_name]
    await init_beanie(database=db, document_models=ALL_DOCUMENT_MODELS)
    await ensure_indexes()


async def ensure_indexes() -> None:
    """Create indexes for all Beanie document models (safe to call on every startup)."""
    for model in ALL_DOCUMENT_MODELS:
        await model.build_indexes()


def get_client() -> AsyncIOMotorClient:
    """Return the Motor client. Use for low-level access (e.g. custom aggregations)."""
    if _client is None:
        raise RuntimeError("DB not initialized; call init_db() first (e.g. in app lifespan).")
    return _client


def get_db() -> AsyncIOMotorDatabase:
    """Return the Motor database. Use for key-based search on raw collections."""
    settings = get_settings()
    return get_client()[settings.mongodb_db_name]


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
    global _client
    if _client is not None:
        _client.close()
        _client = None
