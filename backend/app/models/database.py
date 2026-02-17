from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie

from app.config import get_settings
from app.models.documents import ALL_DOCUMENT_MODELS

_client: AsyncIOMotorClient | None = None


async def init_db() -> None:
    """Initialize MongoDB connection and Beanie ODM."""
    global _client
    settings = get_settings()
    _client = AsyncIOMotorClient(settings.mongodb_url)
    db = _client[settings.mongodb_db_name]
    await init_beanie(database=db, document_models=ALL_DOCUMENT_MODELS)


async def close_db() -> None:
    """Close MongoDB connection."""
    global _client
    if _client is not None:
        _client.close()
        _client = None
