from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from app.api.sessions import get_session_or_404
from app.models.documents import (
    ShortlistDocument,
    SearchResultDocument,
    CommunicationDocument,
    TestDriveBookingDocument,
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


@router.get("/export-pdf")
async def export_dashboard_pdf(session_id: str):
    """Generate a PDF report of the dashboard using Foxit Document Generation API."""
    # Reuse same data loading as get_dashboard
    await get_session_or_404(session_id)

    shortlist = await ShortlistDocument.find_one(
        ShortlistDocument.session_id == session_id
    )
    if not shortlist:
        raise HTTPException(status_code=404, detail="No shortlist found for this session")

    search_doc = await SearchResultDocument.find_one(
        SearchResultDocument.session_id == session_id,
        SearchResultDocument.status == "completed",
    )
    if not search_doc:
        raise HTTPException(status_code=404, detail="No completed search found")

    shortlisted_ids = set(shortlist.vehicle_ids)
    vehicles = [
        v for v in search_doc.vehicles
        if v.get("vehicle_id") in shortlisted_ids
    ]

    comms = await CommunicationDocument.find(
        CommunicationDocument.session_id == session_id
    ).to_list()
    comm_status = [
        {
            "vehicle_id": c.vehicle_id,
            "text_sent": c.comm_type == "text" and c.status == "sent",
            "call_made": c.comm_type == "call" and c.status == "completed",
            "response": c.summary,
            "call_details": c.call_details,
        }
        for c in comms
    ]

    bookings = await TestDriveBookingDocument.find(
        TestDriveBookingDocument.session_id == session_id
    ).to_list()
    bookings_by_vehicle = {
        b.vehicle_id: {
            "scheduled_date": b.scheduled_date or "",
            "scheduled_time": b.scheduled_time or "",
        }
        for b in bookings
    }

    try:
        from app.services.foxit_pdf import prepare_dashboard_data, generate_dashboard_pdf

        data = prepare_dashboard_data(
            vehicles=[{**v} for v in vehicles],
            communication_status=comm_status,
            bookings_by_vehicle=bookings_by_vehicle,
        )
        pdf_bytes = generate_dashboard_pdf(data)
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=f"PDF generation failed: {e}")

    filename = f"dashboard_report_{session_id[:8]}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
