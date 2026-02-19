"""Deepgram + Twilio voice agent for autonomous dealership calls."""

from typing import Optional

from app.config import get_settings
from app.models.documents import CommunicationDocument


async def initiate_voice_call(
    comm_id: str,
    dealer_phone: str,
    vehicle: dict,
    call_purpose: str,
    negotiation_target_price: Optional[float] = None,
) -> None:
    """Initiate an autonomous AI voice call to a dealership.

    This integrates Twilio (for the phone line) with Deepgram Voice Agent API
    (for STT + TTS + LLM orchestration).

    Flow:
    1. Twilio makes outbound call to dealer_phone
    2. Twilio streams audio via WebSocket to our server
    3. Our server bridges audio to Deepgram Voice Agent API
    4. Deepgram handles STT -> LLM -> TTS pipeline
    5. TTS audio streams back through Twilio to the dealer

    This is a stub -- implement the full pipeline when API keys are configured.
    """
    from bson import ObjectId

    comm = await CommunicationDocument.get(ObjectId(comm_id))
    if not comm:
        return

    settings = get_settings()

    if not settings.twilio_account_sid or not settings.deepgram_api_key:
        # Stub mode
        comm.status = "completed"
        comm.duration_seconds = 0
        comm.transcript = [
            {
                "speaker": "agent",
                "text": f"[STUB] Hi, I'm calling about the {vehicle.get('title', 'vehicle')}.",
                "timestamp": 0.0,
            },
            {
                "speaker": "dealer",
                "text": "[STUB] Yes, it's still available!",
                "timestamp": 2.0,
            },
        ]
        comm.summary = (
            f"[STUB] Call completed for {vehicle.get('title', 'vehicle')}. "
            f"Purpose: {call_purpose}."
        )
        await comm.save()
        return

    # TODO: implement real Twilio + Deepgram Voice Agent pipeline
    # Reference: https://developers.deepgram.com/docs/twilio-and-deepgram-voice-agent
    #
    # 1. Create TwiML with <Stream> WebSocket pointing to our /ws/voice endpoint
    # 2. Make outbound call via Twilio REST API
    # 3. Handle WebSocket connection from Twilio
    # 4. Bridge audio to Deepgram Voice Agent WebSocket
    # 5. Collect transcript and update CommunicationDocument
    comm.status = "failed"
    comm.summary = "Real voice pipeline not yet implemented."
    await comm.save()
