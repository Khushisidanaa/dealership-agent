"""
Standalone Twilio + Deepgram voice script.

Run with backend/.env set (or export):
  TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER
  DEEPGRAM_API_KEY
  SERVER_BASE_URL  (public URL, e.g. https://xxx.ngrok-free.app — no trailing slash)
  TO_NUMBER        (optional: number to call when script starts; e.g. +15551234567)

Then:
  python script.py

With TO_NUMBER set, the script will start the server and place one outbound call.
Without TO_NUMBER, it only runs the server (you can trigger calls from elsewhere).

Deps: pip install aiohttp websockets twilio python-dotenv
"""

import asyncio
import base64
import json
import logging
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path

from aiohttp import web

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)

try:
    import aiohttp
    import websockets
    from twilio.rest import Client
    from dotenv import load_dotenv
except ImportError as e:
    print("Install deps: pip install aiohttp websockets twilio python-dotenv")
    sys.exit(1)

load_dotenv()

# ---------------------------------------------------------------------------
# Static context for the voice agent (edit as needed)
# ---------------------------------------------------------------------------

AGENT_PROMPT = """You are a friendly AI assistant calling a car dealership on behalf of a buyer.

The buyer is interested in: 2022 Honda Civic, listed at $24,500.
They have a max budget of $25,000 and are available on Saturdays and Sundays for a test drive.
Purpose of the call: schedule a test drive and ask if the car is still available.

Be concise and natural. State the purpose early. Use the buyer's availability when the dealer asks.
Keep responses to 1-2 sentences.

When the user says goodbye, bye, or wants to end the call, say a brief farewell like "Thanks for your time. Goodbye!" and the call will end."""

GREETING = "Hi, I'm calling to schedule a test drive for the 2022 Honda Civic you have listed, and to check if it's still available."

# ---------------------------------------------------------------------------
# Config from env
# ---------------------------------------------------------------------------

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER", "")
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY", "")
SERVER_BASE_URL = os.getenv("SERVER_BASE_URL", "http://localhost:5000").rstrip("/")
TO_NUMBER = os.getenv("TO_NUMBER", "")  # e.g. +15551234567

PORT = int(os.getenv("PORT", "5000"))


def wss_url():
    if SERVER_BASE_URL.startswith("https://"):
        return SERVER_BASE_URL.replace("https://", "wss://", 1) + "/ws/voice"
    if SERVER_BASE_URL.startswith("http://"):
        return SERVER_BASE_URL.replace("http://", "ws://", 1) + "/ws/voice"
    return f"wss://{SERVER_BASE_URL}/ws/voice"


# ---------------------------------------------------------------------------
# Twilio <-> Deepgram bridge (WebSocket handler)
# ---------------------------------------------------------------------------


def _is_goodbye(text: str) -> bool:
    """Check if text indicates the user wants to end the call."""
    if not text:
        return False
    t = text.lower().strip()
    return any(
        phrase in t
        for phrase in ("bye", "goodbye", "good bye", "good-by", "bye bye", "gotta go", "have to go")
    )


def _write_transcript(transcript: list[tuple[str, str]], output_dir: Path) -> Path | None:
    """Write transcript to a timestamped text file. Returns path or None."""
    if not transcript:
        return None
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = f"call_transcript_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.txt"
    path = output_dir / filename
    with open(path, "w") as f:
        for role, content in transcript:
            label = "User" if role == "user" else "Agent"
            f.write(f"{label}: {content}\n\n")
    log.info("Transcript saved to %s", path)
    return path


async def handle_twilio_voice(ws: web.WebSocketResponse):
    audio_queue = asyncio.Queue()
    streamsid_queue = asyncio.Queue()
    transcript: list[tuple[str, str]] = []
    end_requested = asyncio.Event()
    transcript_dir = Path(__file__).parent / "transcripts"

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
                "prompt": AGENT_PROMPT,
            },
            "speak": {"provider": {"type": "deepgram", "model": "aura-2-thalia-en"}},
            "greeting": GREETING,
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
                        await ws.send_str(
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
                                await ws.close()
                                break
                except json.JSONDecodeError:
                    pass
                continue
            # Binary = TTS audio
            await ws.send_str(
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
        async for msg in ws:
            if msg.type != web.WSMsgType.TEXT:
                break
            try:
                data = json.loads(msg.data)
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
            except (json.JSONDecodeError, KeyError):
                pass
        await audio_queue.put(None)

    try:
        log.info("Connecting to Deepgram Agent...")
        async with websockets.connect(
            "wss://agent.deepgram.com/v1/agent/converse",
            subprotocols=["token", DEEPGRAM_API_KEY],
        ) as dg_ws:
            log.info("Deepgram Agent connected, sending Settings...")
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
        log.exception("Deepgram bridge error: %s\n%s", e, traceback.format_exc())
    finally:
        await ws.close()
        if transcript:
            _write_transcript(transcript, transcript_dir)


# ---------------------------------------------------------------------------
# HTTP server: TwiML + WebSocket
# ---------------------------------------------------------------------------


async def twiml_handler(request: web.Request):
    log.info("TwiML requested by Twilio")
    stream_url = wss_url()
    body = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say language="en">This call may be monitored or recorded.</Say>
    <Connect>
        <Stream url="{stream_url}" />
    </Connect>
</Response>"""
    log.info("TwiML sent, stream_url=%s", stream_url)
    return web.Response(text=body, content_type="application/xml")


async def ws_voice_handler(request: web.Request):
    log.info("WebSocket /ws/voice connected")
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    try:
        await handle_twilio_voice(ws)
    except Exception as e:
        log.exception("WebSocket handler error: %s", e)
        raise
    return ws


def init_app():
    app = web.Application()

    @web.middleware
    async def log_requests(request, handler):
        log.info("%s %s from %s", request.method, request.path, request.remote)
        try:
            return await handler(request)
        except Exception as e:
            log.exception("Request failed: %s", e)
            raise

    app.middlewares.append(log_requests)
    app.router.add_route("GET", "/twiml", twiml_handler)
    app.router.add_route("POST", "/twiml", twiml_handler)
    app.router.add_get("/ws/voice", ws_voice_handler)
    return app


# ---------------------------------------------------------------------------
# Twilio: initiate outbound call
# ---------------------------------------------------------------------------


def place_call():
    if not all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER]):
        print("Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER")
        return
    if not TO_NUMBER:
        print("Set TO_NUMBER in env to place a call (e.g. TO_NUMBER=+15551234567)")
        return
    if not SERVER_BASE_URL or not (
        SERVER_BASE_URL.startswith("http://") or SERVER_BASE_URL.startswith("https://")
    ):
        print(
            "Set SERVER_BASE_URL to your public URL (e.g. https://xxx.ngrok-free.app) so Twilio can reach /twiml."
        )
        return
    twiml_url = f"{SERVER_BASE_URL.rstrip('/')}/twiml"
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    call = client.calls.create(
        to=TO_NUMBER, from_=TWILIO_PHONE_NUMBER, url=twiml_url, timeout=30
    )
    print(f"Call initiated: {call.sid} -> {TO_NUMBER}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main():
    if not DEEPGRAM_API_KEY:
        print("Set DEEPGRAM_API_KEY in .env")
        sys.exit(1)
    app = init_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    print(f"Server listening on 0.0.0.0:{PORT}")
    if SERVER_BASE_URL and (
        SERVER_BASE_URL.startswith("http://") or SERVER_BASE_URL.startswith("https://")
    ):
        base = SERVER_BASE_URL.rstrip("/")
        print(f"  TwiML: {base}/twiml")
        print(f"  WS:    {wss_url()}")
    else:
        print(
            "  Set SERVER_BASE_URL in .env to your public URL (e.g. from ngrok) to see TwiML and WebSocket URLs."
        )
    if TO_NUMBER:
        place_call()
    else:
        print("Set TO_NUMBER to place a test call when the script starts.")
    print("Press Ctrl+C to stop.")
    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(main())
