"""
Vehicle listings search endpoint (MarketCheck API).
"""

from fastapi import APIRouter, HTTPException

from app.models.schemas import (
    VehicleListingSearchRequest,
    VehicleListingSearchResponse,
)
from app.services.marketcheck_service import search_listings

router = APIRouter(prefix="/api/listings", tags=["listings"])


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
