from fastapi import APIRouter, BackgroundTasks

from app.api.sessions import get_session_or_404
from app.models.documents import SearchResultDocument
from app.models.schemas import (
    SearchTriggerResponse,
    SearchStatusResponse,
    SearchResultsResponse,
    VehicleResult,
    PriceStats,
)
from app.services.scraper_service import run_search

router = APIRouter(prefix="/api/sessions/{session_id}/search", tags=["search"])


@router.post("", response_model=SearchTriggerResponse, status_code=202)
async def trigger_search(session_id: str, background_tasks: BackgroundTasks):
    """Trigger web scraping with all accumulated preferences."""
    session = await get_session_or_404(session_id)

    search_doc = SearchResultDocument(session_id=session_id)
    await search_doc.insert()

    session.status = "searching"
    await session.save()

    # Run scraping in background
    background_tasks.add_task(
        run_search,
        search_doc.search_id,
        session.preferences or {},
        session.additional_filters or {},
    )

    return SearchTriggerResponse(
        search_id=search_doc.search_id,
        status=search_doc.status,
        estimated_time_seconds=30,
    )


@router.get("/{search_id}/status", response_model=SearchStatusResponse)
async def get_search_status(session_id: str, search_id: str):
    """Poll search progress."""
    await get_session_or_404(session_id)

    doc = await SearchResultDocument.find_one(
        SearchResultDocument.search_id == search_id
    )
    if not doc:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Search not found")

    return SearchStatusResponse(
        search_id=doc.search_id,
        status=doc.status,
        progress_percent=doc.progress_percent,
        results_count=len(doc.vehicles),
    )


@router.get("/{search_id}/results", response_model=SearchResultsResponse)
async def get_search_results(session_id: str, search_id: str):
    """Get all scraped results with comparison data."""
    await get_session_or_404(session_id)

    doc = await SearchResultDocument.find_one(
        SearchResultDocument.search_id == search_id
    )
    if not doc:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Search not found")

    vehicles = [VehicleResult(**v) for v in doc.vehicles]
    price_stats = PriceStats(**doc.price_stats) if doc.price_stats else None

    return SearchResultsResponse(results=vehicles, price_stats=price_stats)
