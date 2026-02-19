"""Test drive booking tools for the LangGraph agent."""

from uuid import uuid4

from langchain_core.tools import tool

from app.config import get_settings


@tool
def book_test_drive_sms(
    phone: str,
    vehicle_id: str,
    vehicle_title: str,
    date: str,
    time: str,
    user_name: str,
) -> dict:
    """Book a test drive by sending a confirmation request SMS to the dealer.

    Args:
        phone: Dealer phone number in E.164 format.
        vehicle_id: ID of the vehicle to test drive.
        vehicle_title: Human-readable vehicle title for the SMS.
        date: Preferred date (YYYY-MM-DD).
        time: Preferred time (HH:MM).
        user_name: Name of the person booking.

    Returns:
        Dict with booking_id and status.
    """
    settings = get_settings()
    booking_id = str(uuid4())

    body = (
        f"Hi, {user_name} would like to schedule a test drive for the "
        f"{vehicle_title} on {date} at {time}. "
        f"Please confirm or suggest an alternative time. Thank you!"
    )

    if not settings.twilio_account_sid:
        return {
            "booking_id": booking_id,
            "status": "pending_confirmation",
            "message": f"[STUB] {body}",
        }

    try:
        from twilio.rest import Client
        client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
        client.messages.create(
            body=body,
            from_=settings.twilio_phone_number,
            to=phone,
        )
        return {
            "booking_id": booking_id,
            "status": "pending_confirmation",
            "message": body,
        }
    except Exception as e:
        return {
            "booking_id": booking_id,
            "status": "failed",
            "error": str(e),
        }


BOOKING_TOOLS = [book_test_drive_sms]
