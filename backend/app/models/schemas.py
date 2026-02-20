from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------

class SessionResponse(BaseModel):
    session_id: str
    user_id: str
    created_at: datetime


# ---------------------------------------------------------------------------
# User requirements / preferences (stored in session.preferences)
# ---------------------------------------------------------------------------

class CarType(str, Enum):
    SUV = "suv"
    SEDAN = "sedan"
    HATCHBACK = "hatchback"
    COUPE = "coupe"
    TRUCK = "truck"
    VAN = "van"
    WAGON = "wagon"
    CONVERTIBLE = "convertible"
    OTHER = "other"


class PowerType(str, Enum):
    GASOLINE = "gasoline"
    DIESEL = "diesel"
    HYBRID = "hybrid"
    PLUGIN_HYBRID = "plugin_hybrid"
    ELECTRIC = "electric"
    EREV = "erev"  # extended-range electric
    FLEX = "flex"
    OTHER = "other"


class FinanceOption(str, Enum):
    CASH = "cash"
    FINANCE = "finance"
    LEASE = "lease"
    UNDECIDED = "undecided"


class RequirementTag(str, Enum):
    """Use case / lifestyle: sporty, outdoor, family, etc."""
    SPORTY = "sporty"
    OUTDOOR = "outdoor"
    FAMILY = "family"
    STUDENT = "student"
    COMMUTE = "commute"
    LUXURY = "luxury"
    OFFROAD = "offroad"
    TOWING = "towing"
    ECONOMY = "economy"
    OTHER = "other"


class UserRequirements(BaseModel):
    """
    Structured user requirements for car search and negotiation.
    Stored in MongoDB (e.g. session.preferences or a dedicated collection).
    """

    # Price & budget
    price_min: float = Field(default=0, ge=0, description="Minimum price (USD)")
    price_max: float = Field(default=100_000, ge=0, description="Maximum price (USD)")
    monthly_budget: Optional[float] = Field(default=None, ge=0, description="Max monthly payment if financing")
    down_payment: Optional[float] = Field(default=None, ge=0, description="Planned down payment (USD)")

    # Location & search area
    zip_code: str = Field(default="", description="User zip for dealer distance")
    max_distance_miles: int = Field(default=50, ge=1, le=500, description="Max distance to dealership (miles)")

    # Brand & model
    brand_preference: list[str] = Field(default_factory=list, description="Preferred makes, e.g. ['Toyota', 'Honda']")
    model_preference: list[str] = Field(default_factory=list, description="Preferred models")
    excluded_brands: list[str] = Field(default_factory=list, description="Makes to exclude")
    excluded_models: list[str] = Field(default_factory=list, description="Models to exclude")

    # Vehicle type & power
    car_type: list[CarType] = Field(default_factory=list, description="Body types: SUV, sedan, etc.")
    power_type: list[PowerType] = Field(default_factory=list, description="Powertrain: electric, hybrid, etc.")

    # Year, condition, mileage
    year_min: int = Field(default=2015, ge=1990, le=2030)
    year_max: int = Field(default=2026, ge=1990, le=2030)
    condition: str = Field(default="any", description="new | used | certified | any")
    max_mileage: Optional[int] = Field(default=None, ge=0, description="Max odometer for used cars")

    # Transmission & features
    transmission: str = Field(default="any", description="auto | manual | any")
    features: list[str] = Field(default_factory=list, description="Must-have features: sunroof, AWD, leather, etc.")
    color_preference: list[str] = Field(default_factory=list, description="Preferred colors")

    # Finance
    finance: FinanceOption = Field(default=FinanceOption.UNDECIDED)
    credit_score: Optional[int] = Field(default=None, ge=300, le=850, description="Approximate credit score if known")

    # Use case / lifestyle (sporty, outdoor, family, student, etc.)
    requirements: list[RequirementTag] = Field(default_factory=list, description="Sporty, outdoor, family, student, etc.")

    # Trade-in
    trade_in: Optional[str] = Field(default=None, description="Trade-in description or 'none'")

    # Free-form
    other_notes: str = Field(default="", description="Other requirements or notes")

    model_config = {"use_enum_values": True}


# ---------------------------------------------------------------------------
# Preferences (API: submit preferences for a session)
# ---------------------------------------------------------------------------

class PreferencesRequest(BaseModel):
    """Legacy/flat preferences submit; can be merged into UserRequirements."""
    make: str = ""
    model: str = ""
    year_min: int = 2015
    year_max: int = 2026
    price_min: float = 0
    price_max: float = 100_000
    condition: str = "any"  # "new" | "used" | "any"
    zip_code: str = ""
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
# Listings search (MarketCheck API)
# ---------------------------------------------------------------------------


class VehicleListingSearchRequest(BaseModel):
    """User preferences for searching vehicle listings via MarketCheck."""

    make: str = Field(..., description="Make, e.g. Toyota, Honda")
    model: str = Field(..., description="Model, e.g. Camry, Accord")
    year: Optional[int] = Field(default=None, ge=1990, le=2030, description="Target year; omit for any year")
    year_min: Optional[int] = Field(default=None, ge=1990, le=2030, description="Minimum year")
    year_max: Optional[int] = Field(default=None, ge=1990, le=2030, description="Maximum year")
    zip_code: str = Field(..., description="ZIP code for proximity search")
    radius_miles: int = Field(default=50, ge=1, le=500, description="Search radius in miles")
    car_type: str = Field(
        default="used",
        description="Listing type: new | used | certified",
    )
    price_min: Optional[int] = Field(default=None, ge=0, description="Minimum price (USD)")
    price_max: Optional[int] = Field(default=None, ge=0, description="Maximum price (USD)")
    max_mileage: Optional[int] = Field(default=None, ge=0, description="Maximum odometer (miles)")
    rows: int = Field(default=20, ge=1, le=50, description="Number of results to return")


# Nested models for comprehensive listing display
class CarfaxInfo(BaseModel):
    one_owner: bool = False
    clean_title: bool = False


class ColorInfo(BaseModel):
    exterior: str = ""
    interior: str = ""
    exterior_base: str = ""
    interior_base: str = ""


class DealerInfo(BaseModel):
    id: Optional[int] = None
    name: str = ""
    phone: str = ""
    website: str = ""
    dealer_type: str = ""
    street: str = ""
    city: str = ""
    state: str = ""
    zip: str = ""
    country: str = ""
    latitude: Optional[str] = None
    longitude: Optional[str] = None
    full_address: str = ""


class BuildInfo(BaseModel):
    year: Optional[int] = None
    make: str = ""
    model: str = ""
    trim: str = ""
    version: str = ""
    body_type: str = ""
    vehicle_type: str = ""
    transmission: str = ""
    drivetrain: str = ""
    fuel_type: str = ""
    engine: str = ""
    engine_size: Optional[float] = None
    doors: Optional[int] = None
    cylinders: Optional[int] = None
    std_seating: str = ""
    highway_mpg: Optional[int] = None
    city_mpg: Optional[int] = None
    powertrain_type: str = ""
    made_in: str = ""


class MediaInfo(BaseModel):
    photo_links: list[str] = Field(default_factory=list)
    photo_links_cached: list[str] = Field(default_factory=list)


class VehicleListingResult(BaseModel):
    """Comprehensive vehicle listing for frontend display."""

    vehicle_id: str
    vin: str = ""
    rank: int
    heading: str = ""
    title: str = ""
    price: Optional[float] = None
    msrp: Optional[float] = None
    miles: Optional[int] = None
    stock_no: str = ""
    days_on_market: Optional[int] = None

    carfax: CarfaxInfo = Field(default_factory=CarfaxInfo)
    colors: ColorInfo = Field(default_factory=ColorInfo)

    seller_type: str = ""
    inventory_type: str = ""

    dealer: DealerInfo = Field(default_factory=DealerInfo)
    dealer_distance_miles: Optional[float] = None

    build: BuildInfo = Field(default_factory=BuildInfo)
    media: MediaInfo = Field(default_factory=MediaInfo)
    image_urls: list[str] = Field(
        default_factory=list,
        description="Primary display images (photo_links, fallback to cached)",
    )

    listing_url: str = ""
    source: str = ""
    in_transit: bool = False


class VehicleListingSearchResponse(BaseModel):
    """Response with vehicle listings and optional price stats for frontend display."""

    results: list[VehicleListingResult]
    total_found: int
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
    call_details: Optional[dict] = None


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


# ---------------------------------------------------------------------------
# Voice API (standalone call endpoint)
# ---------------------------------------------------------------------------


class VoiceCallRequest(BaseModel):
    """Params for initiating an AI voice call. Prompt and start_message are derived from user conversation."""

    to_number: str = Field(..., description="E.164 phone number to call, e.g. +15551234567")
    prompt: str = Field(
        ...,
        description="Agent context/instructions derived from user preferences (vehicle, budget, purpose, etc.)",
    )
    start_message: str = Field(
        ...,
        description="Opening line the agent says when the call connects (greeting)",
    )


class VoiceCallResponse(BaseModel):
    call_id: str
    status: str = "initiating"
    to_number: str
    twiml_url: str


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


# ---------------------------------------------------------------------------
# Document analysis (Foxit: Carfax, inspection reports, etc.)
# ---------------------------------------------------------------------------

class DocumentAnalysisResponse(BaseModel):
    extracted_text: str
    summary: Optional[str] = None
    filename: str = ""


# ---------------------------------------------------------------------------
# Dealership directory (from Maps; not per-user)
# ---------------------------------------------------------------------------

class Dealership(BaseModel):
    """Dealership directory entry from Google/Apple Maps."""
    dealer_id: str
    name: str = ""
    address: str = ""
    phone: str = ""
    website: str = ""
    lat: Optional[float] = None
    lng: Optional[float] = None
    source: str = "google_maps"
    rating: Optional[float] = None
    types: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Dealership contact (dealers we contacted for a user)
# ---------------------------------------------------------------------------

class DealershipContactStatus(str, Enum):
    TEXT = "text"
    CALL = "call"
    RESPONDED = "responded"


class DealerCar(BaseModel):
    """Minimal car info at a dealership; expand into full model later."""
    vehicle_id: str = ""
    title: str = ""
    price: Optional[float] = None
    listing_url: str = ""


class DealershipContact(BaseModel):
    """
    Data for a dealership we contacted. Keyed by user_id + dealer_id.
    """
    dealer_id: str
    user_id: str
    dealership_name: str = ""
    address: str = ""
    distance_miles: Optional[float] = Field(default=None, description="Rough distance from user location")
    status: DealershipContactStatus = Field(default=DealershipContactStatus.TEXT)
    cars: list[DealerCar] = Field(default_factory=list)

    model_config = {"use_enum_values": True}
