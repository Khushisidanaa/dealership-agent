from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter

import logging

from app.api.sessions import get_session_or_404
from app.models.documents import SearchResultDocument
from app.models.schemas import (
    SearchResultsResponse,
    SearchTriggerResponse,
    SearchStatusResponse,
    VehicleResult,
    VehicleListingResult,
)
from app.services.marketcheck_service import search_listings

log = logging.getLogger(__name__)

MAX_PER_DEALER = 5

router = APIRouter(prefix="/api/sessions/{session_id}/search", tags=["search"])


def _flatten_listing(r, rank: int) -> dict:
    """Flatten a VehicleListingResult into the Vehicle shape the frontend expects."""
    dealer = r.dealer if r.dealer else None
    build = r.build if r.build else None

    features = []
    if build:
        if build.transmission and build.transmission != "any":
            features.append(build.transmission)
        if build.drivetrain:
            features.append(build.drivetrain)
        if build.fuel_type:
            features.append(build.fuel_type)
        if build.body_type:
            features.append(build.body_type)

    return {
        "vehicle_id": r.vehicle_id or f"mc-{rank}",
        "rank": rank,
        "title": r.title or r.heading or "Unknown Vehicle",
        "price": r.price or 0,
        "mileage": r.miles,
        "condition": r.inventory_type or "used",
        "dealer_name": dealer.name if dealer else "",
        "dealer_phone": dealer.phone if dealer else "",
        "dealer_address": dealer.full_address if dealer else "",
        "dealer_distance_miles": r.dealer_distance_miles,
        "listing_url": r.listing_url or "",
        "image_urls": r.image_urls or [],
        "features": features,
        "condition_score": 0,
        "price_score": 0,
        "overall_score": 0,
        "known_issues": [],
        "source": r.source or "marketcheck",
        "vin": r.vin or "",
        "year": build.year if build else None,
        "make": build.make if build else "",
        "model": build.model if build else "",
    }


def _resolve_make_model(merged: dict) -> tuple[str, str]:
    """Extract make/model from merged preferences, falling back to brand_preference/model_preference arrays."""
    make = merged.get("make", "") or ""
    model = merged.get("model", "") or ""

    if not make and merged.get("brand_preference"):
        brands = merged["brand_preference"]
        if isinstance(brands, list) and brands:
            make = str(brands[0])

    if not model and merged.get("model_preference"):
        models = merged["model_preference"]
        if isinstance(models, list) and models:
            model = str(models[0])

    return make, model


def _limit_per_dealer(vehicles: list[dict], max_per_dealer: int = MAX_PER_DEALER) -> list[dict]:
    """Cap results per dealer for diversity, preserving original rank order."""
    by_dealer: dict[str, list[dict]] = defaultdict(list)
    for v in vehicles:
        dealer = v.get("dealer_name") or "Unknown"
        if len(by_dealer[dealer]) < max_per_dealer:
            by_dealer[dealer].append(v)
    result = [v for group in by_dealer.values() for v in group]
    result.sort(key=lambda v: v.get("rank", 999))
    return result


async def _run_search(session_id: str) -> tuple[list[dict], dict | None, str]:
    """Search MarketCheck for vehicles matching session preferences."""
    session = await get_session_or_404(session_id)
    prefs = session.preferences or {}
    extra = session.additional_filters or {}
    merged = {**prefs, **extra}

    make, model = _resolve_make_model(merged)
    zip_code = merged.get("zip_code", "") or "90210"
    radius = int(merged.get("radius_miles") or merged.get("max_distance_miles") or 50)
    year_min = merged.get("year_min")
    year_max = merged.get("year_max")
    price_min = merged.get("price_min")
    price_max = merged.get("price_max")
    max_mileage = merged.get("max_mileage")
    condition = merged.get("condition", "used") or "used"

    log.info("Search params: make=%s model=%s zip=%s radius=%s", make, model, zip_code, radius)

    try:
        results, total, price_stats_obj = await search_listings(
            make=make,
            model=model,
            zip_code=zip_code,
            radius_miles=radius,
            car_type=condition,
            year_min=int(year_min) if year_min else None,
            year_max=int(year_max) if year_max else None,
            price_min=int(price_min) if price_min else None,
            price_max=int(price_max) if price_max else None,
            max_mileage=int(max_mileage) if max_mileage else None,
            rows=50,
        )
    except Exception as exc:
        log.exception("MarketCheck search failed: %s", exc)
        results, total, price_stats_obj = [], 0, None

    all_vehicles = [_flatten_listing(r, i + 1) for i, r in enumerate(results)]
    vehicles = _limit_per_dealer(all_vehicles)
    for i, v in enumerate(vehicles):
        v["rank"] = i + 1
    price_stats = price_stats_obj.model_dump() if price_stats_obj else None

    search_doc = await SearchResultDocument.find_one(
        SearchResultDocument.session_id == session_id,
        SearchResultDocument.status == "completed",
    )
    if search_doc:
        search_doc.vehicles = vehicles
        search_doc.price_stats = price_stats
        await search_doc.save()
    else:
        search_doc = SearchResultDocument(
            session_id=session_id,
            status="completed",
            progress_percent=100,
            vehicles=vehicles,
            price_stats=price_stats,
        )
        await search_doc.insert()

    return vehicles, price_stats, str(search_doc.id)


@router.post("", response_model=SearchTriggerResponse)
async def trigger_search(session_id: str):
    """Trigger a search. Runs synchronously and returns immediately with a search_id."""
    vehicles, _, search_id = await _run_search(session_id)
    return SearchTriggerResponse(
        search_id=search_id,
        status="completed",
        estimated_time_seconds=0,
    )


@router.get("/{search_id}/status", response_model=SearchStatusResponse)
async def get_search_status(session_id: str, search_id: str):
    """Check search status. Since search runs synchronously, always returns completed."""
    search_doc = await SearchResultDocument.find_one(
        SearchResultDocument.session_id == session_id,
    )
    results_count = len(search_doc.vehicles) if search_doc and search_doc.vehicles else 0
    return SearchStatusResponse(
        search_id=search_id,
        status="completed",
        progress_percent=100,
        results_count=results_count,
    )


@router.get("/{search_id}/results")
async def get_search_results(session_id: str, search_id: str):
    """Get search results."""
    search_doc = await SearchResultDocument.find_one(
        SearchResultDocument.session_id == session_id,
    )
    if not search_doc:
        return {"results": [], "price_stats": None}

    return {
        "results": search_doc.vehicles or [],
        "price_stats": search_doc.price_stats,
    }


@router.get("/cars")
async def search_cars_in_area(session_id: str):
    """Direct search endpoint (alternative). Runs search and returns results."""
    from app.models.documents import SessionDocument
    vehicles, price_stats, _ = await _run_search(session_id)
    await SessionDocument.find_one(
        SessionDocument.session_id == session_id
    ).update({"$set": {"phase": "results"}})
    return {"results": vehicles, "price_stats": price_stats}
