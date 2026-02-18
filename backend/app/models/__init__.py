"""
Models package: MongoDB documents (Beanie), API schemas, and DB driver utilities.

Documents (stored in Mongo):
  - SessionDocument, ChatMessageDocument, SearchResultDocument,
  - ShortlistDocument, CommunicationDocument, TestDriveBookingDocument,
  - UserRequirementsDocument (keyed by user_id)
  - DealershipContactDocument (keyed by user_id + dealer_id)

DB driver (app/models/database.py):
  - init_db, close_db
  - get_db_handler() -> DBHandler (create once at startup, pass around; insert/get/update/delete by model type)
  - get_client(), get_db() for raw access
  - find_one_by_keys(collection_name, **keys), find_many_by_keys(...) for index-backed search

User requirements (app/models/user_requirements.py):
  - create_user_requirements, get_user_requirements, update_user_requirements, delete_user_requirements
"""
from app.models.database import (
    init_db,
    close_db,
    get_db_handler,
    get_client,
    get_db,
    find_one_by_keys,
    find_many_by_keys,
)
from app.models.db_handler import DBHandler
from app.models.documents import (
    ALL_DOCUMENT_MODELS,
    SessionDocument,
    ChatMessageDocument,
    SearchResultDocument,
    ShortlistDocument,
    CommunicationDocument,
    TestDriveBookingDocument,
    UserRequirementsDocument,
    DealershipContactDocument,
)
from app.models.user_requirements import (
    create_user_requirements,
    get_user_requirements,
    update_user_requirements,
    delete_user_requirements,
)
from app.models import schemas

__all__ = [
    "init_db",
    "close_db",
    "get_db_handler",
    "DBHandler",
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
    "UserRequirementsDocument",
    "DealershipContactDocument",
    "create_user_requirements",
    "get_user_requirements",
    "update_user_requirements",
    "delete_user_requirements",
    "schemas",
]
