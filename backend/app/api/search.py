from fastapi import APIRouter

from app.api.sessions import get_session_or_404
from app.models.documents import SearchResultDocument
from app.models.schemas import SearchResultsResponse, VehicleResult
from app.services.scraper_service import search_cars

router = APIRouter(prefix="/api/sessions/{session_id}/search", tags=["search"])


@router.get("/cars", response_model=SearchResultsResponse)
async def search_cars_in_area(session_id: str):
    """Find cars matching the user's requirements in the area. Results are stored for dashboard."""
    session = await get_session_or_404(session_id)
    prefs = session.preferences or {}
    extra = session.additional_filters or {}
    requirements = {**prefs, **extra}
    requirements.setdefault("zip_code", requirements.get("zip_code") or prefs.get("zip_code") or "90210")
    requirements.setdefault("radius_miles", int(requirements.get("radius_miles") or requirements.get("max_distance_miles") or prefs.get("radius_miles") or 50))

    vehicles = await search_cars(requirements, [])

    price_stats = None
    if vehicles:
        prices = [v["price"] for v in vehicles]
        price_stats = {
            "avg_market_price": round(sum(prices) / len(prices), 2),
            "lowest_price": min(prices),
            "highest_price": max(prices),
        }

    # Persist so dashboard can load shortlist + vehicles
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

    return SearchResultsResponse(
        results=[VehicleResult(**v) for v in vehicles],
        price_stats=price_stats,
    )
