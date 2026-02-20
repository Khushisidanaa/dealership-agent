from fastapi import APIRouter, HTTPException

from app.api.sessions import get_session_or_404
from app.models.documents import (
    ShortlistDocument,
    SearchResultDocument,
    CommunicationDocument,
)
from app.models.schemas import (
    ShortlistRequest,
    ShortlistResponse,
    ShortlistEntry,
    DashboardResponse,
    VehicleResult,
    CommunicationStatusOut,
)

router = APIRouter(prefix="/api/sessions/{session_id}", tags=["dashboard"])


@router.post("/shortlist", response_model=ShortlistResponse)
async def create_shortlist(session_id: str, body: ShortlistRequest):
    """AI auto-selects or user manually picks top vehicles."""
    await get_session_or_404(session_id)

    # TODO: if body.auto_select, run scoring_service to pick top 4
    shortlist = ShortlistDocument(
        session_id=session_id,
        vehicle_ids=body.vehicle_ids,
        auto_selected=body.auto_select,
    )
    await shortlist.insert()

    entries = [
        ShortlistEntry(vehicle_id=vid, rank=idx + 1, overall_score=0.0)
        for idx, vid in enumerate(body.vehicle_ids)
    ]
    return ShortlistResponse(shortlisted=entries)


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(session_id: str):
    """Get full dashboard data for the KendoReact view."""
    await get_session_or_404(session_id)

    shortlist = await ShortlistDocument.find_one(
        ShortlistDocument.session_id == session_id
    )
    if not shortlist:
        raise HTTPException(status_code=404, detail="No shortlist found for this session")

    # Fetch vehicle data from latest search results
    search_doc = await SearchResultDocument.find_one(
        SearchResultDocument.session_id == session_id,
        SearchResultDocument.status == "completed",
    )
    if not search_doc:
        raise HTTPException(status_code=404, detail="No completed search found")

    shortlisted_ids = set(shortlist.vehicle_ids)
    vehicles = [
        VehicleResult(**v)
        for v in search_doc.vehicles
        if v.get("vehicle_id") in shortlisted_ids
    ]

    # Fetch communication status
    comms = await CommunicationDocument.find(
        CommunicationDocument.session_id == session_id
    ).to_list()

    comm_status = [
        CommunicationStatusOut(
            vehicle_id=c.vehicle_id,
            text_sent=c.comm_type == "text" and c.status == "sent",
            call_made=c.comm_type == "call" and c.status == "completed",
            response=c.summary,
            call_details=c.call_details,
        )
        for c in comms
    ]

    return DashboardResponse(
        shortlist=vehicles,
        comparison_chart=None,  # TODO: build chart data from scoring_service
        communication_status=comm_status,
    )
