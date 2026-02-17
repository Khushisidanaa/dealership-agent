from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------

class SessionResponse(BaseModel):
    session_id: str
    created_at: datetime


# ---------------------------------------------------------------------------
# Preferences
# ---------------------------------------------------------------------------

class PreferencesRequest(BaseModel):
    make: str
    model: str
    year_min: int = 2015
    year_max: int = 2026
    price_min: float = 0
    price_max: float = 100_000
    condition: str = "any"  # "new" | "used" | "any"
    zip_code: str
    radius_miles: int = 50
    max_mileage: Optional[int] = None


class PreferencesResponse(BaseModel):
    session_id: str
    preferences_saved: bool
    next_step: str = "chat"


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str
    updated_filters: Optional[dict] = None
    is_ready_to_search: bool = False


class ChatMessageOut(BaseModel):
    role: str
    content: str
    timestamp: datetime


class ChatHistoryResponse(BaseModel):
    messages: list[ChatMessageOut]


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

class SearchTriggerResponse(BaseModel):
    search_id: str
    status: str
    estimated_time_seconds: int = 30


class SearchStatusResponse(BaseModel):
    search_id: str
    status: str
    progress_percent: int
    results_count: int = 0


class VehicleResult(BaseModel):
    vehicle_id: str
    rank: int
    title: str
    price: float
    mileage: Optional[int] = None
    condition: str
    dealer_name: str
    dealer_phone: str = ""
    dealer_address: str = ""
    dealer_distance_miles: Optional[float] = None
    listing_url: str = ""
    image_urls: list[str] = Field(default_factory=list)
    features: list[str] = Field(default_factory=list)
    condition_score: float = 0.0
    price_score: float = 0.0
    overall_score: float = 0.0
    known_issues: list[str] = Field(default_factory=list)
    source: str = ""


class PriceStats(BaseModel):
    avg_market_price: float
    lowest_price: float
    highest_price: float


class SearchResultsResponse(BaseModel):
    results: list[VehicleResult]
    price_stats: Optional[PriceStats] = None


# ---------------------------------------------------------------------------
# Shortlist / Dashboard
# ---------------------------------------------------------------------------

class ShortlistRequest(BaseModel):
    vehicle_ids: list[str] = Field(default_factory=list)
    auto_select: bool = False


class ShortlistEntry(BaseModel):
    vehicle_id: str
    rank: int
    overall_score: float


class ShortlistResponse(BaseModel):
    shortlisted: list[ShortlistEntry]


class CommunicationStatusOut(BaseModel):
    vehicle_id: str
    text_sent: bool = False
    call_made: bool = False
    response: Optional[str] = None


class DashboardResponse(BaseModel):
    shortlist: list[VehicleResult]
    comparison_chart: Optional[dict] = None
    communication_status: list[CommunicationStatusOut] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Communication
# ---------------------------------------------------------------------------

class TextRequest(BaseModel):
    vehicle_id: str
    message_template: str = "inquiry"  # inquiry | negotiate | test_drive


class TextResponse(BaseModel):
    text_id: str
    status: str
    dealer_phone: str
    message_body: str


class CallRequest(BaseModel):
    vehicle_id: str
    call_purpose: str = "inquiry"  # inquiry | negotiate | book_test_drive
    negotiation_target_price: Optional[float] = None


class CallTriggerResponse(BaseModel):
    call_id: str
    status: str
    dealer_phone: str


class TranscriptEntry(BaseModel):
    speaker: str
    text: str
    timestamp: float


class CallStatusResponse(BaseModel):
    call_id: str
    status: str
    duration_seconds: Optional[int] = None
    transcript: list[TranscriptEntry] = Field(default_factory=list)
    summary: Optional[str] = None
    recording_url: Optional[str] = None


# ---------------------------------------------------------------------------
# Test Drive
# ---------------------------------------------------------------------------

class TestDriveRequest(BaseModel):
    vehicle_id: str
    preferred_date: str
    preferred_time: str
    user_name: str
    user_phone: str
    user_email: str = ""
    confirm: bool = True


class TestDriveResponse(BaseModel):
    booking_id: str
    status: str
    dealer_name: str = ""
    vehicle_title: str = ""
    scheduled_date: str
    scheduled_time: str


class TestDriveStatusResponse(BaseModel):
    booking_id: str
    status: str
    confirmation_method: Optional[str] = None
    dealer_response: Optional[str] = None
