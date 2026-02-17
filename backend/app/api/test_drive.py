from fastapi import APIRouter, HTTPException

from app.api.sessions import get_session_or_404
from app.models.documents import TestDriveBookingDocument
from app.models.schemas import (
    TestDriveRequest,
    TestDriveResponse,
    TestDriveStatusResponse,
)

router = APIRouter(
    prefix="/api/sessions/{session_id}/test-drive",
    tags=["test-drive"],
)


@router.post("", response_model=TestDriveResponse, status_code=201)
async def book_test_drive(session_id: str, body: TestDriveRequest):
    """Book a test drive at a dealership."""
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

    # TODO: trigger confirmation via Twilio SMS/call to dealer

    return TestDriveResponse(
        booking_id=booking.booking_id,
        status=booking.status,
        scheduled_date=booking.scheduled_date,
        scheduled_time=booking.scheduled_time,
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
