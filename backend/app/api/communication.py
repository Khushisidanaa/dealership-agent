from fastapi import APIRouter, BackgroundTasks, HTTPException

from app.api.sessions import get_session_or_404
from app.models.documents import CommunicationDocument, SearchResultDocument
from app.models.schemas import (
    TextRequest,
    TextResponse,
    CallRequest,
    CallTriggerResponse,
    CallStatusResponse,
    TranscriptEntry,
)
from app.services.twilio_service import send_sms
from app.services.deepgram_service import initiate_voice_call

router = APIRouter(
    prefix="/api/sessions/{session_id}/communication",
    tags=["communication"],
)


async def _get_vehicle_from_search(session_id: str, vehicle_id: str) -> dict:
    """Lookup a vehicle from the latest completed search."""
    search_doc = await SearchResultDocument.find_one(
        SearchResultDocument.session_id == session_id,
        SearchResultDocument.status == "completed",
    )
    if not search_doc:
        raise HTTPException(status_code=404, detail="No completed search found")

    vehicle = next(
        (v for v in search_doc.vehicles if v.get("vehicle_id") == vehicle_id),
        None,
    )
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found in results")
    return vehicle


@router.post("/text", response_model=TextResponse)
async def send_text(session_id: str, body: TextRequest):
    """Send SMS to a dealership via Twilio."""
    await get_session_or_404(session_id)
    vehicle = await _get_vehicle_from_search(session_id, body.vehicle_id)

    dealer_phone = vehicle.get("dealer_phone", "")
    if not dealer_phone:
        raise HTTPException(status_code=400, detail="Dealer phone not available")

    message_body = await send_sms(
        dealer_phone=dealer_phone,
        vehicle=vehicle,
        template=body.message_template,
    )

    comm = CommunicationDocument(
        session_id=session_id,
        vehicle_id=body.vehicle_id,
        comm_type="text",
        status="sent",
        dealer_phone=dealer_phone,
        message_body=message_body,
    )
    await comm.insert()

    return TextResponse(
        text_id=str(comm.id),
        status="sent",
        dealer_phone=dealer_phone,
        message_body=message_body,
    )


@router.post("/call", response_model=CallTriggerResponse, status_code=202)
async def start_call(
    session_id: str,
    body: CallRequest,
    background_tasks: BackgroundTasks,
):
    """Initiate an autonomous AI voice call to a dealership."""
    await get_session_or_404(session_id)
    vehicle = await _get_vehicle_from_search(session_id, body.vehicle_id)

    dealer_phone = vehicle.get("dealer_phone", "")
    if not dealer_phone:
        raise HTTPException(status_code=400, detail="Dealer phone not available")

    comm = CommunicationDocument(
        session_id=session_id,
        vehicle_id=body.vehicle_id,
        comm_type="call",
        status="initiating",
        dealer_phone=dealer_phone,
    )
    await comm.insert()

    background_tasks.add_task(
        initiate_voice_call,
        comm_id=str(comm.id),
        dealer_phone=dealer_phone,
        vehicle=vehicle,
        call_purpose=body.call_purpose,
        negotiation_target_price=body.negotiation_target_price,
    )

    return CallTriggerResponse(
        call_id=str(comm.id),
        status="initiating",
        dealer_phone=dealer_phone,
    )


@router.get("/call/{call_id}", response_model=CallStatusResponse)
async def get_call_status(session_id: str, call_id: str):
    """Get call status and transcript."""
    await get_session_or_404(session_id)

    from bson import ObjectId
    comm = await CommunicationDocument.get(ObjectId(call_id))
    if not comm or comm.session_id != session_id:
        raise HTTPException(status_code=404, detail="Call not found")

    return CallStatusResponse(
        call_id=call_id,
        status=comm.status,
        duration_seconds=comm.duration_seconds,
        transcript=[TranscriptEntry(**t) for t in comm.transcript],
        summary=comm.summary,
        recording_url=comm.recording_url,
    )
