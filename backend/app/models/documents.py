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


class UserDocument(Document):
    """User stored in MongoDB. One doc per user; user_id is the primary key."""
    user_id: str = Field(default_factory=new_uuid)
    name: str = ""
    email: Optional[str] = None
    password_hash: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)

    class Settings:
        name = "users"
        indexes = [
            "user_id",
            pymongo.IndexModel([("user_id", pymongo.ASCENDING)], unique=True),
        ]


class SessionDocument(Document):
    session_id: str = Field(default_factory=new_uuid)
    created_at: datetime = Field(default_factory=utc_now)
    status: str = Field(default="created")
    phase: str = Field(default="chat")

    user_id: Optional[str] = None

    preferences: Optional[dict] = None
    additional_filters: Optional[dict] = None

    class Settings:
        name = "sessions"
        indexes = [
            "session_id",
            "user_id",
            [("created_at", pymongo.DESCENDING)],
            [("user_id", pymongo.ASCENDING), ("created_at", pymongo.DESCENDING)],
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
    call_details: Optional[dict] = None
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
    call_transcript: Optional[str] = None
    call_result: Optional[dict] = None
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


class DealershipDocument(Document):
    """
    Directory of dealerships (from Google/Apple Maps). Not per-user.
    dealer_id = place_id (or external id) for linking with DealershipContact.
    """
    dealer_id: str  # e.g. Google place_id; unique
    name: str = ""
    address: str = ""
    phone: str = ""
    website: str = ""
    lat: Optional[float] = None
    lng: Optional[float] = None
    source: str = "google_maps"  # google_maps | apple_maps
    rating: Optional[float] = None
    types: list[str] = Field(default_factory=list)  # e.g. ["car_dealer", "point_of_interest"]
    raw: Optional[dict] = None  # extra from Maps API
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    class Settings:
        name = "dealerships"
        indexes = [
            "dealer_id",
            "source",
            pymongo.IndexModel([("dealer_id", pymongo.ASCENDING)], unique=True),
        ]


ALL_DOCUMENT_MODELS = [
    UserDocument,
    SessionDocument,
    ChatMessageDocument,
    SearchResultDocument,
    ShortlistDocument,
    CommunicationDocument,
    TestDriveBookingDocument,
    UserRequirementsDocument,
    DealershipContactDocument,
    DealershipDocument,
]
