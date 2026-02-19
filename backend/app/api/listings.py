"""
Vehicle listings search endpoint (MarketCheck API).
"""

from fastapi import APIRouter, HTTPException

from app.api.sessions import get_session_or_404
from app.models.documents import UserDocument
from app.models.schemas import (
    VehicleListingSearchRequest,
    VehicleListingSearchResponse,
)
from app.models.user_requirements import get_user_requirements
from app.services.marketcheck_service import search_listings

router = APIRouter(prefix="/api/listings", tags=["listings"])


def _requirements_to_listings_request(prefs: dict) -> VehicleListingSearchRequest:
    """Build listings search request from user requirements / session preferences."""
    make = "Toyota"
    model = "Camry"
    if prefs.get("brand_preference"):
        brands = prefs["brand_preference"]
        if isinstance(brands, list) and len(brands) > 0:
            make = str(brands[0])
    if prefs.get("model_preference"):
        models = prefs["model_preference"]
        if isinstance(models, list) and len(models) > 0:
            model = str(models[0])
    zip_code = prefs.get("zip_code") or "90210"
    radius = int(prefs.get("max_distance_miles") or prefs.get("radius_miles") or 50)
    condition = (prefs.get("condition") or "any").lower()
    car_type = "used" if condition == "used" else "new" if condition == "new" else "used"
    if condition == "certified":
        car_type = "certified"
    return VehicleListingSearchRequest(
        make=make,
        model=model,
        year_min=prefs.get("year_min"),
        year_max=prefs.get("year_max"),
        zip_code=zip_code,
        radius_miles=radius,
        car_type=car_type,
        price_min=prefs.get("price_min"),
        price_max=prefs.get("price_max"),
        max_mileage=prefs.get("max_mileage"),
        rows=30,
    )


@router.get("/by-session/{session_id}", response_model=VehicleListingSearchResponse)
async def get_listings_for_session(session_id: str):
    """
    Search vehicle listings using the session's saved requirements (from chat / requirements modal).
    Uses MarketCheck API. Use this when the user opens the dashboard.
    """
    session = await get_session_or_404(session_id)
    if not session.user_id:
        user = UserDocument()
        await user.insert()
        session.user_id = user.user_id
        await session.save()
    user_id = session.user_id
    prefs = session.preferences or {}
    req_obj = await get_user_requirements(user_id)
    if req_obj:
        prefs = {**prefs, **req_obj.model_dump()}
    req = _requirements_to_listings_request(prefs)
    try:
        results, total_found, price_stats = await search_listings(
            make=req.make,
            model=req.model,
            year=req.year,
            year_min=req.year_min,
            year_max=req.year_max,
            zip_code=req.zip_code,
            radius_miles=req.radius_miles,
            car_type=req.car_type,
            price_min=req.price_min,
            price_max=req.price_max,
            max_mileage=req.max_mileage,
            rows=req.rows,
        )
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Listing search failed: {str(e)}",
        ) from e
    return VehicleListingSearchResponse(
        results=results,
        total_found=total_found,
        price_stats=price_stats,
    )


@router.post("/search", response_model=VehicleListingSearchResponse)
async def search_vehicle_listings(req: VehicleListingSearchRequest):
    """
    Search vehicle listings by user preferences.
    Uses MarketCheck API; returns results formatted for frontend display.
    """
    try:
        results, total_found, price_stats = await search_listings(
            make=req.make,
            model=req.model,
            year=req.year,
            year_min=req.year_min,
            year_max=req.year_max,
            zip_code=req.zip_code,
            radius_miles=req.radius_miles,
            car_type=req.car_type,
            price_min=req.price_min,
            price_max=req.price_max,
            max_mileage=req.max_mileage,
            rows=req.rows,
        )
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Listing search failed: {str(e)}",
        ) from e

    return VehicleListingSearchResponse(
        results=results,
        total_found=total_found,
        price_stats=price_stats,
    )
