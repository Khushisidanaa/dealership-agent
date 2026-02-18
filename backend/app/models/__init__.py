"""
Models package: MongoDB documents (Beanie), API schemas, and DB driver utilities.

Documents (stored in Mongo):
  - SessionDocument, ChatMessageDocument, SearchResultDocument,
  - ShortlistDocument, CommunicationDocument, TestDriveBookingDocument

DB driver (app/models/database.py):
  - init_db, close_db, ensure_indexes
  - get_client(), get_db() for raw access
  - find_one_by_keys(collection_name, **keys), find_many_by_keys(...) for index-backed search
"""
from app.models.database import (
    init_db,
    close_db,
    ensure_indexes,
    get_client,
    get_db,
    find_one_by_keys,
    find_many_by_keys,
)
from app.models.documents import (
    ALL_DOCUMENT_MODELS,
    SessionDocument,
    ChatMessageDocument,
    SearchResultDocument,
    ShortlistDocument,
    CommunicationDocument,
    TestDriveBookingDocument,
)
from app.models import schemas

__all__ = [
    "init_db",
    "close_db",
    "ensure_indexes",
    "get_client",
    "get_db",
    "find_one_by_keys",
    "find_many_by_keys",
    "ALL_DOCUMENT_MODELS",
    "SessionDocument",
    "ChatMessageDocument",
    "SearchResultDocument",
    "ShortlistDocument",
    "CommunicationDocument",
    "TestDriveBookingDocument",
    "schemas",
]
