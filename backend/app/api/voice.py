"""
Voice call API: Twilio + voice agent (Amazon Nova Sonic or Deepgram) for autonomous dealership calls.

Same flow for both: POST /api/voice/call → Twilio calls dealer → TwiML → WebSocket → bridge to voice agent.
Uses Nova Sonic when AWS credentials are configured; otherwise Deepgram.
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
from app.services.nova_sonic_service import has_nova_sonic_configured, run_nova_sonic_bridge

log = logging.getLogger(__name__)
# Use uvicorn's logger so voice/Nova diagnostics show in the same console as "connection open"
voice_log = logging.getLogger("uvicorn.error")

router = APIRouter(prefix="/api/voice", tags=["voice"])

# In-memory store for call context (call_id -> {agent_prompt, greeting})
# Twilio fetches TwiML asynchronously when the call connects
_call_context: dict[str, dict] = {}
_transcript_dir = Path(__file__).parent.parent.parent / "transcripts"
_completed_calls_dir = Path(__file__).parent.parent.parent / "completed_calls"

# Completed call results keyed by call_id.  Populated when the WS bridge finishes.
# Also persisted under completed_calls/{call_id}.json so GET works across workers/restarts.
_completed_calls: dict[str, dict] = {}


def _persist_completed_call(call_id: str, payload: dict) -> None:
    """Write completed call result to disk so GET /api/voice/call/{id} works across workers."""
    try:
        _completed_calls_dir.mkdir(parents=True, exist_ok=True)
        path = _completed_calls_dir / f"{call_id}.json"
        with open(path, "w") as f:
            json.dump(payload, f, indent=0)
    except Exception as e:
        log.warning("Could not persist completed call %s: %s", call_id, e)


def _load_completed_call(call_id: str) -> dict | None:
    """Read completed call result from disk if not in memory."""
    try:
        path = _completed_calls_dir / f"{call_id}.json"
        if path.exists():
            with open(path) as f:
                return json.load(f)
    except Exception as e:
        log.debug("Could not load completed call %s: %s", call_id, e)
    return None


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

    if not has_nova_sonic_configured() and not settings.deepgram_api_key:
        raise HTTPException(
            status_code=503,
            detail="Voice not configured: set AWS credentials (ACCESS_KEY/SECRET_ACCRESS_KEY) for Nova Sonic or DEEPGRAM_API_KEY",
        )

    base = settings.server_base_url.rstrip("/")
    if not base.startswith("http") or "127.0.0.1" in base or "localhost" in base:
        raise HTTPException(
            status_code=503,
            detail=(
                "Set SERVER_BASE_URL to a public URL so Twilio can reach your server for the call. "
                "When running locally: start ngrok (e.g. ngrok http 8000), then set SERVER_BASE_URL to the https URL ngrok shows (no trailing slash)."
            ),
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

    log.info("Placing voice call to: %s (from=%s)", req.to_number, settings.twilio_phone_number)
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
        msg = exc.msg or str(exc)
        if "unverified" in msg.lower() or "verified" in msg.lower():
            raise HTTPException(
                status_code=400,
                detail=(
                    "Twilio trial account: you can only call verified numbers. "
                    "Add and verify the dealer number in Twilio Console → Phone Numbers → Manage → Verified Caller IDs, "
                    "or upgrade your Twilio account to call any number."
                ),
            )
        raise HTTPException(status_code=502, detail=f"Twilio error: {msg}")

    log.info("Call initiated: calling %s (Twilio sid=%s, call_id=%s)", req.to_number, call.sid, call_id)

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


async def _handle_twilio_voice_nova(websocket: WebSocket, call_id: str):
    """Bridge Twilio Media Stream to Amazon Nova Sonic (same flow as Deepgram)."""
    voice_log.info("Nova voice: WebSocket connected call_id=%s", call_id)
    ctx = _call_context.get(call_id, {})
    agent_prompt = ctx.get("agent_prompt", "You are a friendly AI assistant.")
    greeting = ctx.get("greeting", "Hi, how can I help you?")

    audio_in_queue: asyncio.Queue = asyncio.Queue()
    audio_out_queue: asyncio.Queue = asyncio.Queue()
    streamsid_queue: asyncio.Queue = asyncio.Queue()
    transcript: list[tuple[str, str]] = []
    end_event = asyncio.Event()

    # Twilio Media Streams: 8kHz mulaw, 20ms = 160 bytes per chunk (see Twilio Media Streams WebSocket docs)
    # Use 20ms chunks for low latency; buffering more delays the model's response (e.g. 30s before speaking)
    TWILIO_CHUNK_BYTES = 160

    async def twilio_receiver():
        inbuffer = bytearray()
        media_events = 0
        try:
            while True:
                msg = await websocket.receive_text()
                data = json.loads(msg)
                if data.get("event") == "start":
                    streamsid_queue.put_nowait(data.get("start", {}).get("streamSid"))
                    voice_log.info("Nova voice: Twilio stream start")
                if data.get("event") == "media":
                    media = data.get("media", {})
                    if media.get("track") == "inbound":
                        media_events += 1
                        if media_events == 1:
                            voice_log.info("Nova voice: first inbound media from Twilio")
                        inbuffer.extend(base64.b64decode(media.get("payload", "")))
                if data.get("event") == "stop":
                    voice_log.info("Nova voice: Twilio stream stop (received %d media events)", media_events)
                    break
                while len(inbuffer) >= TWILIO_CHUNK_BYTES:
                    await audio_in_queue.put(bytes(inbuffer[:TWILIO_CHUNK_BYTES]))
                    inbuffer = inbuffer[TWILIO_CHUNK_BYTES:]
        except WebSocketDisconnect:
            voice_log.info("Nova voice: Twilio WebSocket disconnected")
        except Exception as e:
            log.exception("Twilio receiver: %s", e)
        finally:
            await audio_in_queue.put(None)

    async def nova_sender():
        stream_sid = await streamsid_queue.get()
        voice_log.info("Nova voice: got stream_sid, waiting for TTS from Nova Sonic...")
        # Twilio expects 160-byte (20ms) mulaw payloads per "media" message; other sizes can cause static/distortion
        outbuffer = bytearray()
        out_count = 0
        while True:
            chunk = await audio_out_queue.get()
            if chunk is None:
                # Flush remainder
                while len(outbuffer) >= TWILIO_CHUNK_BYTES:
                    frame = bytes(outbuffer[:TWILIO_CHUNK_BYTES])
                    outbuffer = outbuffer[TWILIO_CHUNK_BYTES:]
                    out_count += 1
                    await websocket.send_text(
                        json.dumps(
                            {
                                "event": "media",
                                "streamSid": stream_sid,
                                "media": {"payload": base64.b64encode(frame).decode("ascii")},
                            }
                        )
                    )
                voice_log.info("Nova voice: nova_sender done, sent %d frames to Twilio", out_count)
                break
            outbuffer.extend(chunk)
            if out_count == 0 and len(outbuffer) >= TWILIO_CHUNK_BYTES:
                voice_log.info("Nova voice: first TTS frame to Twilio")
            while len(outbuffer) >= TWILIO_CHUNK_BYTES:
                frame = bytes(outbuffer[:TWILIO_CHUNK_BYTES])
                outbuffer = outbuffer[TWILIO_CHUNK_BYTES:]
                out_count += 1
                await websocket.send_text(
                    json.dumps(
                        {
                            "event": "media",
                            "streamSid": stream_sid,
                            "media": {"payload": base64.b64encode(frame).decode("ascii")},
                        }
                    )
                )

    tasks: list[asyncio.Task] = []
    try:
        voice_log.info("Nova voice: starting bridge, twilio_receiver, nova_sender tasks")
        bridge_task = asyncio.create_task(
            run_nova_sonic_bridge(
                agent_prompt, greeting, audio_in_queue, audio_out_queue, transcript, end_event
            )
        )
        recv_task = asyncio.create_task(twilio_receiver())
        sender_task = asyncio.create_task(nova_sender())
        tasks = [recv_task, bridge_task, sender_task]
        await asyncio.gather(*tasks)
        voice_log.info("Nova voice: all tasks finished")
    except Exception as e:
        log.exception("Nova Sonic bridge error: %s", e)
        for t in tasks:
            if not t.done():
                t.cancel()
        for t in tasks:
            try:
                await t
            except asyncio.CancelledError:
                pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
        payload = {
            "status": "completed",
            "transcript": list(transcript),
            "transcript_text": "\n".join(
                f"{'Agent' if r == 'agent' else 'Dealer'}: {c}" for r, c in transcript
            ),
        }
        _completed_calls[call_id] = payload
        _persist_completed_call(call_id, payload)
        if transcript:
            _write_transcript(transcript)
        _call_context.pop(call_id, None)


async def _handle_twilio_voice_deepgram(websocket: WebSocket, call_id: str):
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
        payload = {
            "status": "completed",
            "transcript": list(transcript),
            "transcript_text": "\n".join(
                f"{'Agent' if r == 'agent' else 'Dealer'}: {c}" for r, c in transcript
            ),
        }
        _completed_calls[call_id] = payload
        _persist_completed_call(call_id, payload)
        if transcript:
            _write_transcript(transcript)
        _call_context.pop(call_id, None)


async def _handle_twilio_voice(websocket: WebSocket, call_id: str):
    """Bridge Twilio Media Stream to voice agent (Nova Sonic or Deepgram)."""
    if has_nova_sonic_configured():
        await _handle_twilio_voice_nova(websocket, call_id)
    else:
        await _handle_twilio_voice_deepgram(websocket, call_id)


@router.get("/call/{call_id}")
async def get_call_result(call_id: str):
    """Poll for a completed call transcript. Always returns transcript_text and transcript for consistent shape."""
    if call_id in _completed_calls:
        out = dict(_completed_calls[call_id])
        out.setdefault("transcript_text", "")
        out.setdefault("transcript", [])
        return out
    # Check disk so polling works across workers or after restart
    persisted = _load_completed_call(call_id)
    if persisted:
        persisted.setdefault("transcript_text", "")
        persisted.setdefault("transcript", [])
        _completed_calls[call_id] = persisted  # cache so we don't re-read
        return persisted
    if call_id in _call_context:
        return {"status": "in_progress", "transcript_text": "", "transcript": []}
    return {"status": "unknown", "transcript_text": "", "transcript": []}


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
