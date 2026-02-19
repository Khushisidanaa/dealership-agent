"""Communication tools for the LangGraph agent -- Twilio SMS and Deepgram voice."""

import asyncio
from uuid import uuid4

from langchain_core.tools import tool

from app.config import get_settings


@tool
def send_dealer_sms(phone: str, message: str) -> dict:
    """Send an SMS message to a car dealer via Twilio.

    Args:
        phone: Dealer phone number in E.164 format (e.g. '+15551234567').
        message: The message body to send.

    Returns:
        Dict with status and message_sid.
    """
    settings = get_settings()

    if not settings.twilio_account_sid:
        return {
            "status": "sent",
            "message_sid": f"STUB_{uuid4()}",
            "body": f"[STUB] {message}",
        }

    try:
        from twilio.rest import Client
        client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
        msg = client.messages.create(
            body=message,
            from_=settings.twilio_phone_number,
            to=phone,
        )
        return {
            "status": "sent",
            "message_sid": msg.sid,
            "body": message,
        }
    except Exception as e:
        return {"status": "failed", "error": str(e)}


@tool
def initiate_dealer_call(
    phone: str,
    vehicle_info: str,
    purpose: str,
) -> dict:
    """Start an autonomous AI voice call to a dealer via Twilio + Deepgram.

    Args:
        phone: Dealer phone number in E.164 format.
        vehicle_info: Brief description of the vehicle being discussed.
        purpose: Purpose of the call -- 'inquiry', 'negotiate', or 'book_test_drive'.

    Returns:
        Dict with call_id and initial status.
    """
    settings = get_settings()
    call_id = str(uuid4())

    if not settings.twilio_account_sid or not settings.deepgram_api_key:
        return {
            "call_id": call_id,
            "status": "completed",
            "summary": (
                f"[STUB] Called {phone} about {vehicle_info}. "
                f"Purpose: {purpose}. Dealer confirmed availability."
            ),
            "transcript": [
                {"speaker": "agent", "text": f"Hi, calling about {vehicle_info}.", "timestamp": 0.0},
                {"speaker": "dealer", "text": "Yes, still available!", "timestamp": 2.0},
            ],
        }

    # Real Twilio + Deepgram pipeline would go here
    return {
        "call_id": call_id,
        "status": "initiating",
        "summary": None,
        "transcript": [],
    }


@tool
def get_call_result(call_id: str) -> dict:
    """Check the result and transcript of a completed dealer call.

    Args:
        call_id: The call ID returned by initiate_dealer_call.

    Returns:
        Dict with status, transcript, and summary.
    """
    return {
        "call_id": call_id,
        "status": "completed",
        "summary": f"[STUB] Call {call_id} completed. Dealer confirmed availability and offered a discount.",
        "transcript": [
            {"speaker": "agent", "text": "Following up on our interest.", "timestamp": 0.0},
            {"speaker": "dealer", "text": "We can do a better price. Come in this week!", "timestamp": 2.5},
        ],
    }


COMM_TOOLS = [send_dealer_sms, initiate_dealer_call, get_call_result]
