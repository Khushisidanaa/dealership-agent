from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

import pymongo
from beanie import Document
from pydantic import Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_uuid() -> str:
    return str(uuid4())


class SessionDocument(Document):
    session_id: str = Field(default_factory=new_uuid)
    created_at: datetime = Field(default_factory=utc_now)
    status: str = Field(default="created")

    # Static preferences
    preferences: Optional[dict] = None

    # Additional filters from conversational agent
    additional_filters: Optional[dict] = None

    class Settings:
        name = "sessions"
        indexes = [
            "session_id",
            [("created_at", pymongo.DESCENDING)],
        ]


class ChatMessageDocument(Document):
    session_id: str
    role: str  # "user" | "assistant"
    content: str
    updated_filters: Optional[dict] = None
    timestamp: datetime = Field(default_factory=utc_now)

    class Settings:
        name = "chat_messages"
        indexes = [
            "session_id",
            [("session_id", pymongo.ASCENDING), ("timestamp", pymongo.ASCENDING)],
        ]


class SearchResultDocument(Document):
    session_id: str
    search_id: str = Field(default_factory=new_uuid)
    status: str = Field(default="scraping")  # scraping | analyzing | completed | failed
    progress_percent: int = Field(default=0)
    vehicles: list[dict] = Field(default_factory=list)
    price_stats: Optional[dict] = None
    created_at: datetime = Field(default_factory=utc_now)

    class Settings:
        name = "search_results"
        indexes = [
            "search_id",
            "session_id",
            [("session_id", pymongo.ASCENDING), ("created_at", pymongo.DESCENDING)],
        ]


class ShortlistDocument(Document):
    session_id: str
    vehicle_ids: list[str] = Field(default_factory=list)
    auto_selected: bool = False
    created_at: datetime = Field(default_factory=utc_now)

    class Settings:
        name = "shortlists"
        indexes = ["session_id"]


class CommunicationDocument(Document):
    session_id: str
    vehicle_id: str
    comm_type: str  # "text" | "call"
    status: str = Field(default="pending")
    dealer_phone: str = ""
    message_body: Optional[str] = None
    transcript: list[dict] = Field(default_factory=list)
    summary: Optional[str] = None
    duration_seconds: Optional[int] = None
    recording_url: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)

    class Settings:
        name = "communications"
        indexes = [
            "session_id",
            [("session_id", pymongo.ASCENDING), ("vehicle_id", pymongo.ASCENDING)],
        ]


class TestDriveBookingDocument(Document):
    session_id: str
    booking_id: str = Field(default_factory=new_uuid)
    vehicle_id: str
    status: str = Field(default="pending_confirmation")
    user_name: str = ""
    user_phone: str = ""
    user_email: str = ""
    scheduled_date: str = ""
    scheduled_time: str = ""
    dealer_response: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)

    class Settings:
        name = "test_drive_bookings"
        indexes = [
            "booking_id",
            "session_id",
            [("session_id", pymongo.ASCENDING), ("created_at", pymongo.DESCENDING)],
        ]


class UserRequirementsDocument(Document):
    """User requirements keyed by user_id (one doc per user)."""
    user_id: str
    requirements: dict = Field(default_factory=dict)  # shape of UserRequirements
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    class Settings:
        name = "user_requirements"
        indexes = [
            "user_id",
            pymongo.IndexModel([("user_id", pymongo.ASCENDING)], unique=True),
        ]


class DealershipContactDocument(Document):
    """Dealerships we contacted for a user. Access by user_id and dealer_id."""
    dealer_id: str
    user_id: str
    dealership_name: str = ""
    address: str = ""
    distance_miles: Optional[float] = None
    status: str = "text"  # text | call | responded
    cars: list[dict] = Field(default_factory=list)  # list of DealerCar-shaped dicts
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    class Settings:
        name = "dealership_contacts"
        indexes = [
            "user_id",
            pymongo.IndexModel(
                [("user_id", pymongo.ASCENDING), ("dealer_id", pymongo.ASCENDING)],
                unique=True,
            ),
        ]


ALL_DOCUMENT_MODELS = [
    SessionDocument,
    ChatMessageDocument,
    SearchResultDocument,
    ShortlistDocument,
    CommunicationDocument,
    TestDriveBookingDocument,
    UserRequirementsDocument,
    DealershipContactDocument,
]
