"""Node: contact_dealers -- calls shortlisted dealers using Twilio + Deepgram.

For each shortlisted vehicle, builds a context-rich prompt and fires off
a voice call via the existing /api/voice/call endpoint. Collects call_ids
so the summarize_calls node can retrieve transcripts later.
"""

from __future__ import annotations

import asyncio
import logging

import httpx
from langchain_core.messages import AIMessage

from app.agent.state import AgentState
from app.agent.prompts.dealer_call import (
    build_dealer_call_prompt,
    build_dealer_call_greeting,
)
from app.config import get_settings

log = logging.getLogger(__name__)


async def _initiate_call(
    base_url: str,
    phone: str,
    prompt: str,
    greeting: str,
) -> dict:
    """POST to /api/voice/call to start a Twilio+Deepgram call."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{base_url}/api/voice/call",
            json={
                "to_number": phone,
                "prompt": prompt,
                "start_message": greeting,
            },
        )
        if resp.status_code != 200:
            return {"error": resp.text, "status": "failed"}
        return resp.json()


async def _poll_call(base_url: str, call_id: str, timeout: int = 300) -> dict:
    """Poll GET /api/voice/call/{call_id} until completed or timeout."""
    async with httpx.AsyncClient(timeout=10) as client:
        elapsed = 0
        interval = 5
        while elapsed < timeout:
            await asyncio.sleep(interval)
            elapsed += interval
            try:
                resp = await client.get(f"{base_url}/api/voice/call/{call_id}")
                data = resp.json()
                if data.get("status") == "completed":
                    return data
            except Exception as exc:
                log.warning("Poll error for call %s: %s", call_id, exc)
    return {"status": "timeout", "transcript_text": "", "transcript": []}


def contact_dealers(state: AgentState) -> dict:
    """Contact each shortlisted dealer by phone. Returns call metadata.

    Runs the async call logic in a new event loop since LangGraph nodes
    are synchronous.
    """
    settings = get_settings()
    vehicles = state.get("vehicles", [])
    shortlist_ids = state.get("shortlist_ids", [])
    preferences = state.get("preferences", {})

    shortlisted = [v for v in vehicles if v.get("vehicle_id") in shortlist_ids]

    if not shortlisted:
        return {
            "communications": [],
            "dealer_responses": [],
            "current_phase": "summarize",
            "messages": [AIMessage(content="No shortlisted vehicles to contact.")],
        }

    has_twilio = (
        settings.twilio_account_sid
        and settings.twilio_auth_token
        and settings.twilio_phone_number
    )
    has_deepgram = bool(settings.deepgram_api_key)
    base_url = settings.server_base_url.rstrip("/")
    has_valid_url = base_url.startswith("http") and "your-subdomain" not in base_url

    if not (has_twilio and has_deepgram and has_valid_url):
        return _stub_calls(shortlisted, preferences)

    return _real_calls(shortlisted, preferences, base_url)


def _real_calls(
    shortlisted: list[dict],
    preferences: dict,
    base_url: str,
) -> dict:
    """Initiate real voice calls and wait for transcripts."""
    comms = []
    user_name = preferences.get("user_name", "Alex")
    budget_max = preferences.get("price_max", 100_000)
    user_zip = preferences.get("zip_code", "")
    financing_interest = preferences.get("finance", "undecided") != "cash"
    trade_in = preferences.get("trade_in", "")

    async def _run_all():
        tasks = []
        for vehicle in shortlisted:
            phone = vehicle.get("dealer_phone", "")
            if not phone:
                continue

            prompt = build_dealer_call_prompt(
                vehicle_title=vehicle.get("title", "vehicle"),
                listing_price=vehicle.get("price", 0),
                vehicle_year=str(vehicle.get("year", "")),
                vehicle_features=vehicle.get("features", []),
                user_budget_max=budget_max,
                user_zip=user_zip,
                user_name=user_name,
                financing_interest=financing_interest,
                trade_in_description=trade_in,
            )
            greeting = build_dealer_call_greeting(
                vehicle_title=vehicle.get("title", "vehicle"),
                dealer_name=vehicle.get("dealer_name", ""),
            )
            tasks.append((vehicle, phone, prompt, greeting))

        results = []
        for vehicle, phone, prompt, greeting in tasks:
            call_resp = await _initiate_call(base_url, phone, prompt, greeting)
            call_id = call_resp.get("call_id", "")

            if call_id:
                transcript_data = await _poll_call(base_url, call_id)
            else:
                transcript_data = {"status": "failed", "transcript_text": ""}

            results.append({
                "vehicle_id": vehicle.get("vehicle_id"),
                "dealer_phone": phone,
                "dealer_name": vehicle.get("dealer_name", ""),
                "call_id": call_id,
                "status": transcript_data.get("status", "unknown"),
                "transcript_text": transcript_data.get("transcript_text", ""),
                "transcript": transcript_data.get("transcript", []),
                "vehicle_title": vehicle.get("title", ""),
                "listing_price": vehicle.get("price", 0),
                "listing_url": vehicle.get("listing_url", ""),
            })
        return results

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                results = pool.submit(
                    lambda: asyncio.run(_run_all())
                ).result(timeout=600)
        else:
            results = loop.run_until_complete(_run_all())
    except Exception as exc:
        log.exception("Error during dealer calls: %s", exc)
        results = []

    completed = [r for r in results if r["status"] == "completed"]
    msg = (
        f"Called {len(results)} dealers. "
        f"{len(completed)} calls completed with transcripts."
    )

    return {
        "communications": results,
        "dealer_responses": results,
        "current_phase": "summarize",
        "messages": [AIMessage(content=msg)],
    }


def _stub_calls(shortlisted: list[dict], preferences: dict) -> dict:
    """Generate realistic stub transcripts for development/demo."""
    comms = []

    stub_conversations = [
        {
            "is_available": True,
            "condition_notes": "Clean title, one previous owner, no accidents reported",
            "best_price": 0.92,
            "dealer_vibe": "helpful",
            "financing": True,
        },
        {
            "is_available": True,
            "condition_notes": "Two previous owners, minor fender bender in 2022, fully repaired",
            "best_price": 0.88,
            "dealer_vibe": "neutral",
            "financing": True,
        },
        {
            "is_available": False,
            "condition_notes": "Sold yesterday",
            "best_price": None,
            "dealer_vibe": "helpful",
            "financing": False,
        },
        {
            "is_available": True,
            "condition_notes": "Clean title, fleet vehicle, regular maintenance on file",
            "best_price": 0.95,
            "dealer_vibe": "pushy",
            "financing": True,
        },
    ]

    for i, vehicle in enumerate(shortlisted):
        phone = vehicle.get("dealer_phone", "+15550000000")
        title = vehicle.get("title", "vehicle")
        price = vehicle.get("price", 25000)
        dealer_name = vehicle.get("dealer_name", f"Dealer {i+1}")
        stub = stub_conversations[i % len(stub_conversations)]

        if stub["is_available"]:
            negotiated = int(price * stub["best_price"]) if stub["best_price"] else price
            transcript_lines = [
                f"Agent: Hi there! I'm calling about the {title} you have listed at {dealer_name}. Is that one still available?",
                f"Dealer: Yes, it is! Are you looking to come in and see it?",
                f"Agent: Definitely interested. Can you tell me about the condition? Any accident history or mechanical issues?",
                f"Dealer: {stub['condition_notes']}. It's in great shape.",
                f"Agent: Good to hear. What's the best out-the-door price on that one?",
                f"Dealer: The listed price is ${price:,.0f}, and with taxes and fees it comes to about ${negotiated + 1200:,.0f} out the door.",
                f"Agent: Is there any flexibility on that price?",
                f"Dealer: We could probably do ${negotiated:,.0f} plus tax and fees if you come in this week.",
            ]
            if stub["financing"]:
                transcript_lines.extend([
                    f"Agent: Do you guys offer financing? What kind of rates?",
                    f"Dealer: Yes, we work with several lenders. Rates are running about 4.9 to 7.9 percent depending on credit.",
                ])
            transcript_lines.extend([
                f"Agent: What are your hours? Could I schedule a test drive?",
                f"Dealer: We're open Monday through Saturday, 9 to 7. Just come on by or call ahead.",
                f"Agent: Great, thanks for all the info. I'll pass this along and they'll probably reach out to schedule something.",
                f"Dealer: Sounds good, we'll be here!",
            ])
        else:
            transcript_lines = [
                f"Agent: Hi there! I'm calling about the {title} you have listed. Is that one still available?",
                f"Dealer: Unfortunately that one sold yesterday. But we have a few similar ones if you're interested.",
                f"Agent: Ah, that's too bad. What do you have in a similar range?",
                f"Dealer: We have a couple other options. Want me to send you some info?",
                f"Agent: Sure, that would be great. Thanks for letting me know!",
            ]

        transcript_text = "\n".join(transcript_lines)

        comms.append({
            "vehicle_id": vehicle.get("vehicle_id"),
            "dealer_phone": phone,
            "dealer_name": dealer_name,
            "call_id": f"stub-call-{i}",
            "status": "completed",
            "transcript_text": transcript_text,
            "transcript": [(
                "agent" if line.startswith("Agent:") else "dealer",
                line.split(": ", 1)[1] if ": " in line else line,
            ) for line in transcript_lines],
            "vehicle_title": title,
            "listing_price": price,
            "listing_url": vehicle.get("listing_url", ""),
        })

    return {
        "communications": comms,
        "dealer_responses": comms,
        "current_phase": "summarize",
        "messages": [AIMessage(
            content=f"Called {len(comms)} dealers (stub mode). Transcripts ready for summarization."
        )],
    }
