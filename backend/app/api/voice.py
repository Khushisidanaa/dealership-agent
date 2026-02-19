"""
Voice call API: Twilio + Deepgram bridge for autonomous dealership calls.

Single endpoint to initiate calls: POST /api/voice/call
Twilio webhooks: GET/POST /api/voice/twiml, WebSocket /api/voice/ws
"""

import asyncio
import base64
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import (
    APIRouter,
    HTTPException,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import Response

from app.config import get_settings

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/voice", tags=["voice"])

# In-memory store for call context (call_id -> {agent_prompt, greeting})
# Twilio fetches TwiML asynchronously when the call connects
_call_context: dict[str, dict] = {}
_transcript_dir = Path(__file__).parent.parent.parent / "transcripts"

# Completed call results keyed by call_id.  Populated when the WS bridge finishes.
_completed_calls: dict[str, dict] = {}


def _wss_url(base_url: str, call_id: str) -> str:
    """WebSocket URL with call_id in path (avoids query-string issues with ngrok/WebSocket)."""
    path = f"/api/voice/ws/{call_id}"
    if base_url.startswith("https://"):
        return base_url.replace("https://", "wss://", 1) + path
    if base_url.startswith("http://"):
        return base_url.replace("http://", "ws://", 1) + path
    return f"wss://{base_url}{path}"


def _is_goodbye(text: str) -> bool:
    if not text:
        return False
    t = text.lower().strip()
    return any(
        phrase in t
        for phrase in (
            "bye",
            "goodbye",
            "good bye",
            "good-by",
            "bye bye",
            "gotta go",
            "have to go",
        )
    )


def _write_transcript(transcript: list[tuple[str, str]]) -> Optional[Path]:
    if not transcript:
        return None
    _transcript_dir.mkdir(parents=True, exist_ok=True)
    filename = f"call_transcript_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.txt"
    path = _transcript_dir / filename
    with open(path, "w") as f:
        for role, content in transcript:
            label = "User" if role == "user" else "Agent"
            f.write(f"{label}: {content}\n\n")
    log.info("Transcript saved to %s", path)
    return path


from app.models.schemas import VoiceCallRequest, VoiceCallResponse


# ---------------------------------------------------------------------------
# POST /api/voice/call – initiate outbound call
# ---------------------------------------------------------------------------


@router.post("/call", response_model=VoiceCallResponse)
async def initiate_call(req: VoiceCallRequest):
    settings = get_settings()

    if (
        not settings.twilio_account_sid
        or not settings.twilio_auth_token
        or not settings.twilio_phone_number
    ):
        raise HTTPException(status_code=503, detail="Twilio not configured")

    if not settings.deepgram_api_key:
        raise HTTPException(status_code=503, detail="Deepgram not configured")

    base = settings.server_base_url.rstrip("/")
    if not base.startswith("http"):
        raise HTTPException(
            status_code=503,
            detail="Set SERVER_BASE_URL to your public URL (e.g. from ngrok)",
        )

    call_id = str(uuid.uuid4())
    # Append goodbye instruction if not already in prompt
    prompt = req.prompt
    if "goodbye" not in prompt.lower() and "bye" not in prompt.lower():
        prompt += '\n\nWhen the user says goodbye, bye, or wants to end the call, say a brief farewell like "Thanks for your time. Goodbye!" and the call will end.'
    _call_context[call_id] = {
        "agent_prompt": prompt,
        "greeting": req.start_message,
    }

    twiml_url = f"{base}/api/voice/twiml?call_id={call_id}"

    from twilio.rest import Client
    from twilio.base.exceptions import TwilioRestException

    try:
        client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
        call = client.calls.create(
            to=req.to_number,
            from_=settings.twilio_phone_number,
            url=twiml_url,
            timeout=30,
        )
    except TwilioRestException as exc:
        log.error("Twilio call failed: %s", exc.msg)
        _call_context.pop(call_id, None)
        raise HTTPException(status_code=502, detail=f"Twilio error: {exc.msg}")

    log.info("Call initiated: %s -> %s (call_id=%s)", call.sid, req.to_number, call_id)

    return VoiceCallResponse(
        call_id=call_id,
        status="initiating",
        to_number=req.to_number,
        twiml_url=twiml_url,
    )


# ---------------------------------------------------------------------------
# GET/POST /api/voice/twiml – Twilio webhook
# ---------------------------------------------------------------------------


@router.get("/twiml")
@router.post("/twiml")
async def twiml_webhook(
    request: Request,
    call_id: str = Query(..., alias="call_id"),
):
    """Return TwiML for Twilio to connect the call to our WebSocket."""
    if call_id not in _call_context:
        log.warning("Unknown call_id for TwiML: %s", call_id)
    settings = get_settings()
    base = settings.server_base_url.rstrip("/")
    stream_url = _wss_url(base, call_id)

    body = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say language="en">This call may be monitored or recorded.</Say>
    <Connect>
        <Stream url="{stream_url}" />
    </Connect>
</Response>"""
    return Response(content=body, media_type="application/xml")


# ---------------------------------------------------------------------------
# WebSocket /api/voice/ws – Twilio Media Stream
# ---------------------------------------------------------------------------


async def _handle_twilio_voice(websocket: WebSocket, call_id: str):
    """Bridge Twilio Media Stream to Deepgram Voice Agent."""
    import websockets

    ctx = _call_context.get(call_id, {})
    agent_prompt = ctx.get("agent_prompt", "You are a friendly AI assistant.")
    greeting = ctx.get("greeting", "Hi, how can I help you?")

    settings = get_settings()
    dg_key = settings.deepgram_api_key

    audio_queue: asyncio.Queue = asyncio.Queue()
    streamsid_queue: asyncio.Queue = asyncio.Queue()
    transcript: list[tuple[str, str]] = []
    end_requested = asyncio.Event()

    config = {
        "type": "Settings",
        "audio": {
            "input": {"encoding": "mulaw", "sample_rate": 8000},
            "output": {"encoding": "mulaw", "sample_rate": 8000, "container": "none"},
        },
        "agent": {
            "language": "en",
            "listen": {"provider": {"type": "deepgram", "model": "nova-3"}},
            "think": {
                "provider": {
                    "type": "open_ai",
                    "model": "gpt-4o-mini",
                    "temperature": 0.7,
                },
                "prompt": agent_prompt,
            },
            "speak": {"provider": {"type": "deepgram", "model": "aura-2-thalia-en"}},
            "greeting": greeting,
        },
    }

    async def sts_sender(dg_ws):
        while True:
            chunk = await audio_queue.get()
            if chunk is None:
                break
            await dg_ws.send(chunk)

    async def sts_receiver(dg_ws):
        stream_sid = await streamsid_queue.get()
        async for message in dg_ws:
            if end_requested.is_set():
                break
            if isinstance(message, str):
                try:
                    data = json.loads(message)
                    msg_type = data.get("type")
                    if msg_type == "UserStartedSpeaking":
                        await websocket.send_text(
                            json.dumps({"event": "clear", "streamSid": stream_sid})
                        )
                    elif msg_type == "ConversationText":
                        role = data.get("role", "")
                        content = data.get("content", "")
                        if role and content:
                            transcript.append((role, content))
                            if role == "user" and _is_goodbye(content):
                                log.info("User said goodbye, ending call")
                                end_requested.set()
                                await audio_queue.put(None)
                                await websocket.close()
                                return
                except json.JSONDecodeError:
                    pass
                continue
            await websocket.send_text(
                json.dumps(
                    {
                        "event": "media",
                        "streamSid": stream_sid,
                        "media": {"payload": base64.b64encode(message).decode("ascii")},
                    }
                )
            )

    async def twilio_receiver():
        BUFFER_SIZE = 20 * 160
        inbuffer = bytearray()
        try:
            while True:
                msg = await websocket.receive_text()
                data = json.loads(msg)
                if data.get("event") == "start":
                    streamsid_queue.put_nowait(data.get("start", {}).get("streamSid"))
                if data.get("event") == "media":
                    media = data.get("media", {})
                    if media.get("track") == "inbound":
                        inbuffer.extend(base64.b64decode(media.get("payload", "")))
                if data.get("event") == "stop":
                    break
                while len(inbuffer) >= BUFFER_SIZE:
                    await audio_queue.put(bytes(inbuffer[:BUFFER_SIZE]))
                    inbuffer = inbuffer[BUFFER_SIZE:]
        except WebSocketDisconnect:
            pass
        except RuntimeError:
            pass
        except Exception as e:
            log.exception("Twilio receiver: %s", e)
        finally:
            await audio_queue.put(None)

    try:
        async with websockets.connect(
            "wss://agent.deepgram.com/v1/agent/converse",
            subprotocols=["token", dg_key],
        ) as dg_ws:
            await dg_ws.send(json.dumps(config))
            recv_task = asyncio.create_task(twilio_receiver())
            sender_task = asyncio.create_task(sts_sender(dg_ws))
            receiver_task = asyncio.create_task(sts_receiver(dg_ws))
            await asyncio.gather(recv_task, receiver_task)
            sender_task.cancel()
            try:
                await sender_task
            except asyncio.CancelledError:
                pass
    except Exception as e:
        log.exception("Deepgram bridge error: %s", e)
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
        _completed_calls[call_id] = {
            "status": "completed",
            "transcript": list(transcript),
            "transcript_text": "\n".join(
                f"{'Agent' if r == 'agent' else 'Dealer'}: {c}" for r, c in transcript
            ),
        }
        if transcript:
            _write_transcript(transcript)
        _call_context.pop(call_id, None)


@router.get("/call/{call_id}")
async def get_call_result(call_id: str):
    """Poll for a completed call transcript."""
    if call_id in _completed_calls:
        return _completed_calls[call_id]
    if call_id in _call_context:
        return {"status": "in_progress", "transcript_text": ""}
    return {"status": "unknown", "transcript_text": ""}


def get_completed_calls() -> dict[str, dict]:
    """Access from other modules (e.g. the analyze endpoint)."""
    return _completed_calls


@router.websocket("/ws/{call_id}")
async def voice_websocket(websocket: WebSocket, call_id: str):
    """WebSocket endpoint for Twilio Media Stream. call_id in path (like script's /ws/voice)."""
    log.info(
        "WebSocket /ws/%s connected, in_context=%s", call_id, call_id in _call_context
    )

    await websocket.accept()

    if call_id not in _call_context:
        log.warning(
            "Unknown call_id for WebSocket: %r (available: %s)",
            call_id,
            list(_call_context.keys()),
        )
        await websocket.close(code=1008)
        return

    await _handle_twilio_voice(websocket, call_id)
