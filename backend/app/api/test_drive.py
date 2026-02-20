"""Test-drive booking and dealer call endpoints."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException
from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI

from app.api.sessions import get_session_or_404
from app.api.call_utils import initiate_call, poll_for_transcript
from app.agent.prompts.test_drive_call import (
    build_test_drive_prompt,
    build_test_drive_greeting,
    build_test_drive_summary_prompt,
)
from app.config import get_settings
from app.models.documents import (
    SearchResultDocument,
    TestDriveBookingDocument,
)
from app.models.schemas import (
    TestDriveRequest,
    TestDriveResponse,
    TestDriveStatusResponse,
    TestDriveCallRequest,
    TestDriveCallResponse,
)

log = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/sessions/{session_id}/test-drive",
    tags=["test-drive"],
)


def _find_vehicle(vehicles: list[dict], vehicle_id: str) -> dict | None:
    return next((v for v in vehicles if v.get("vehicle_id") == vehicle_id), None)


def _parse_call_result(raw: str) -> dict:
    """Best-effort JSON parse from LLM output."""
    try:
        from app.utils import parse_json_from_llm
        return parse_json_from_llm(raw)
    except Exception:
        pass
    try:
        return json.loads(raw)
    except Exception:
        return {"confirmed": False, "scheduled_date": None, "scheduled_time": None, "dealer_notes": raw[:300]}


@router.post("", response_model=TestDriveResponse, status_code=201)
async def book_test_drive(session_id: str, body: TestDriveRequest):
    """Book a test drive at a dealership (no call -- just saves the booking)."""
    await get_session_or_404(session_id)

    booking = TestDriveBookingDocument(
        session_id=session_id,
        vehicle_id=body.vehicle_id,
        user_name=body.user_name,
        user_phone=body.user_phone,
        user_email=body.user_email,
        scheduled_date=body.preferred_date,
        scheduled_time=body.preferred_time,
    )
    await booking.insert()

    return TestDriveResponse(
        booking_id=booking.booking_id,
        status=booking.status,
        scheduled_date=booking.scheduled_date,
        scheduled_time=booking.scheduled_time,
    )


@router.post("/call", response_model=TestDriveCallResponse)
async def call_dealer_for_test_drive(session_id: str, body: TestDriveCallRequest):
    """Call the dealer to schedule a test drive, poll for result, summarize, and save."""
    await get_session_or_404(session_id)
    settings = get_settings()

    search_doc = await SearchResultDocument.find_one(
        SearchResultDocument.session_id == session_id,
        SearchResultDocument.status == "completed",
    )
    if not search_doc or not search_doc.vehicles:
        raise HTTPException(status_code=400, detail="No search results found for this session.")

    vehicle = _find_vehicle(search_doc.vehicles, body.vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=404, detail=f"Vehicle {body.vehicle_id} not found in search results.")

    vehicle_title = vehicle.get("title", "vehicle")
    dealer_name = vehicle.get("dealer_name", "dealer")
    dealer_phone = vehicle.get("dealer_phone", "")

    override = settings.to_number if settings.to_number and not settings.to_number.startswith("+1555") else ""
    call_phone = override or dealer_phone
    if not call_phone:
        raise HTTPException(status_code=400, detail="No phone number available for this dealer.")

    public_url = settings.server_base_url.rstrip("/")
    if not public_url.startswith("http") or "your-subdomain" in public_url:
        raise HTTPException(status_code=503, detail="SERVER_BASE_URL not configured. Start ngrok and update .env")

    local_url = "http://127.0.0.1:8000"

    prompt = build_test_drive_prompt(
        vehicle_title=vehicle_title,
        dealer_name=dealer_name,
        user_name=body.user_name,
        preferred_date=body.preferred_date,
        preferred_time=body.preferred_time,
    )
    greeting = build_test_drive_greeting(
        vehicle_title=vehicle_title,
        dealer_name=dealer_name,
        user_name=body.user_name,
        preferred_date=body.preferred_date,
        preferred_time=body.preferred_time,
    )

    call_resp = await initiate_call(local_url, call_phone, prompt, greeting)
    call_id = call_resp.get("call_id", "")
    transcript_text = ""

    if call_id and call_resp.get("status") != "failed":
        result = await poll_for_transcript(local_url, call_id, timeout=120)
        transcript_text = result.get("transcript_text", "")

    if not transcript_text:
        booking = TestDriveBookingDocument(
            session_id=session_id,
            vehicle_id=body.vehicle_id,
            user_name=body.user_name,
            scheduled_date=body.preferred_date,
            scheduled_time=body.preferred_time,
            status="call_failed",
            dealer_response="Could not reach dealer.",
        )
        await booking.insert()
        return TestDriveCallResponse(
            booking_id=booking.booking_id,
            status="call_failed",
            confirmed=False,
            dealer_notes="Could not reach the dealer. Try calling them directly.",
            vehicle_title=vehicle_title,
            dealer_name=dealer_name,
        )

    summary_prompt = build_test_drive_summary_prompt(
        vehicle_title=vehicle_title,
        preferred_date=body.preferred_date,
        preferred_time=body.preferred_time,
        transcript_text=transcript_text,
    )

    try:
        llm = ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=0.1,
        )
        response = llm.invoke([SystemMessage(content=summary_prompt)])
        parsed = _parse_call_result(response.content)
    except Exception as exc:
        log.warning("LLM summary failed for test-drive call: %s", exc)
        parsed = {
            "confirmed": False,
            "scheduled_date": None,
            "scheduled_time": None,
            "dealer_notes": "Call completed but could not parse result.",
        }

    is_confirmed = parsed.get("confirmed", False)
    final_date = parsed.get("scheduled_date") or body.preferred_date
    final_time = parsed.get("scheduled_time") or body.preferred_time
    status = "confirmed" if is_confirmed else "declined"

    booking = TestDriveBookingDocument(
        session_id=session_id,
        vehicle_id=body.vehicle_id,
        user_name=body.user_name,
        scheduled_date=final_date,
        scheduled_time=final_time,
        status=status,
        dealer_response=parsed.get("dealer_notes", ""),
        call_transcript=transcript_text,
        call_result=parsed,
    )
    await booking.insert()

    return TestDriveCallResponse(
        booking_id=booking.booking_id,
        status=status,
        confirmed=is_confirmed,
        scheduled_date=final_date,
        scheduled_time=final_time,
        dealer_notes=parsed.get("dealer_notes", ""),
        vehicle_title=vehicle_title,
        dealer_name=dealer_name,
    )


@router.get("/{booking_id}", response_model=TestDriveStatusResponse)
async def get_test_drive_status(session_id: str, booking_id: str):
    """Check test drive booking status."""
    await get_session_or_404(session_id)

    booking = await TestDriveBookingDocument.find_one(
        TestDriveBookingDocument.booking_id == booking_id,
        TestDriveBookingDocument.session_id == session_id,
    )
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    return TestDriveStatusResponse(
        booking_id=booking.booking_id,
        status=booking.status,
        dealer_response=booking.dealer_response,
    )
