"""
POST /api/sessions/{session_id}/analyze  -- The post-search flow.

After search results are in, the frontend calls this endpoint.  It:
  1. Calls each dealer using Twilio + Deepgram (the existing voice API)
  2. Streams progress to the UI via Server-Sent Events (SSE)
  3. Summarises each call transcript into structured data (via LLM)
  4. Ranks vehicles and returns a final top-3

The endpoint returns an SSE stream so the UI can show real-time status.
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.api.sessions import get_session_or_404
from app.api.call_utils import initiate_call, poll_for_transcript
from app.agent.prompts.dealer_call import (
    build_dealer_call_prompt,
    build_dealer_call_greeting,
)
from app.agent.prompts.call_summary import build_summary_prompt
from app.config import get_settings
from app.models.documents import SearchResultDocument, CommunicationDocument, SessionDocument, UserDocument

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/sessions/{session_id}", tags=["analyze"])

# ---------------------------------------------------------------------------
# Testing overrides -- change these for demo / hackathon
# ---------------------------------------------------------------------------
CALL_LIMIT = 1


def _sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def _summarize_transcript(vehicle: dict, transcript_text: str) -> dict:
    """Use OpenAI to extract structured data from a transcript."""
    settings = get_settings()
    prompt_text = build_summary_prompt(
        vehicle_title=vehicle.get("title", ""),
        listing_price=vehicle.get("price", 0),
        listing_url=vehicle.get("listing_url", ""),
        transcript_text=transcript_text,
    )

    from langchain_core.messages import SystemMessage
    from langchain_openai import ChatOpenAI

    llm = ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        temperature=0.1,
    )

    try:
        from app.utils import parse_json_from_llm

        response = llm.invoke([SystemMessage(content=prompt_text)])
        return parse_json_from_llm(response.content)
    except Exception as exc:
        log.warning("LLM summary failed for %s: %s -- falling back to basic parse", vehicle.get("vehicle_id"), exc)
        return _basic_parse(vehicle, transcript_text)


def _basic_parse(vehicle: dict, transcript_text: str) -> dict:
    """Regex-based fallback when LLM is unavailable. Not a stub -- parses real transcripts."""
    import re

    title = vehicle.get("title", "vehicle")
    price = vehicle.get("price", 0)
    text_lower = transcript_text.lower()

    is_available = "sold" not in text_lower and "no longer available" not in text_lower
    is_negotiable = any(kw in text_lower for kw in ("could probably do", "flexibility", "work with you", "negotiate"))
    has_financing = any(kw in text_lower for kw in ("financing", "rates", "apr", "lender"))
    has_accident = any(kw in text_lower for kw in ("accident", "fender", "collision", "body work"))

    best_price = None
    for line in transcript_text.split("\n"):
        ll = line.lower()
        if any(kw in ll for kw in ("could probably do", "we could do", "best price", "out the door")):
            prices = re.findall(r'\$[\d,]+', line)
            if prices:
                best_price = int(prices[0].replace('$', '').replace(',', ''))

    key_parts = []
    if is_available:
        key_parts.append(f"{title} is available.")
    else:
        key_parts.append(f"{title} appears sold or unavailable.")
    if best_price:
        key_parts.append(f"Best quoted: ${best_price:,}.")
    if has_financing:
        key_parts.append("Financing available.")
    key_parts.append("Price negotiable." if is_negotiable else "Price seems firm.")

    return {
        "is_available": is_available,
        "condition": {
            "accident_history": "mentioned in call" if has_accident else "none reported",
            "title_status": "clean" if "clean title" in text_lower else None,
            "overall_notes": "Parsed from transcript",
        },
        "pricing": {
            "listed_price": price,
            "best_quoted_price": best_price,
            "is_negotiable": is_negotiable,
            "out_the_door_price": (best_price + 1200) if best_price else None,
        },
        "financing": {
            "available": has_financing,
            "apr_range": None,
        },
        "dealer_impression": {
            "responsiveness": "unknown",
            "willingness_to_deal": "medium" if is_negotiable else "low",
        },
        "red_flags": ["Accident history mentioned"] if has_accident else [],
        "key_takeaways": " ".join(key_parts),
        "recommendation": "worth visiting" if is_available else "skip",
    }


def _rank_vehicles(vehicles: list[dict], summaries: dict) -> list[dict]:
    scored = []
    for v in vehicles:
        vid = v.get("vehicle_id", "")
        base = v.get("overall_score", 0)
        s = summaries.get(vid, {})

        adj = 0
        if s.get("is_available") is False:
            adj -= 100
        if s.get("recommendation") == "worth visiting":
            adj += 3
        elif s.get("recommendation") == "skip":
            adj -= 50
        pricing = s.get("pricing", {})
        if pricing.get("is_negotiable"):
            adj += 2
        if pricing.get("best_quoted_price") and v.get("price"):
            savings = v["price"] - pricing["best_quoted_price"]
            if savings > 0:
                adj += min(savings / 500, 5)
        if s.get("red_flags"):
            adj -= len(s["red_flags"])
        impression = s.get("dealer_impression", {})
        if impression.get("responsiveness") == "helpful":
            adj += 1
        elif impression.get("responsiveness") == "evasive":
            adj -= 2

        scored.append({**v, "_final_score": base + adj, "_summary": s})

    scored.sort(key=lambda x: x["_final_score"], reverse=True)
    return scored


@router.post("/analyze")
async def analyze_vehicles(session_id: str, request: Request):
    """Call dealers, summarize conversations, rank vehicles. Streams SSE progress."""

    session = await get_session_or_404(session_id)
    settings = get_settings()

    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    requested_ids = body.get("vehicle_ids") if isinstance(body, dict) else None

    search_doc = await SearchResultDocument.find_one(
        SearchResultDocument.session_id == session_id,
        SearchResultDocument.status == "completed",
    )
    if not search_doc or not search_doc.vehicles:
        raise HTTPException(status_code=400, detail="No search results to analyze. Run search first.")

    all_vehicles = search_doc.vehicles

    if requested_ids and isinstance(requested_ids, list):
        id_set = set(requested_ids)
        vehicles = [v for v in all_vehicles if v.get("vehicle_id") in id_set]
        if not vehicles:
            vehicles = all_vehicles[:CALL_LIMIT] if CALL_LIMIT else all_vehicles
    else:
        vehicles = all_vehicles[:CALL_LIMIT] if CALL_LIMIT else all_vehicles

    preferences = session.preferences or {}

    user_name = preferences.get("user_name", "")
    if not user_name and session.user_id:
        user_doc = await UserDocument.find_one(UserDocument.user_id == session.user_id)
        if user_doc and user_doc.name:
            user_name = user_doc.name.split()[0]
    if not user_name:
        user_name = "the buyer"

    public_url = settings.server_base_url.rstrip("/")
    if not public_url.startswith("http") or "your-subdomain" in public_url:
        raise HTTPException(
            status_code=503,
            detail="SERVER_BASE_URL not configured. Start ngrok and update .env",
        )
    local_url = "http://127.0.0.1:8000"

    vehicles_for_ui = [
        {
            "vehicle_id": v.get("vehicle_id", ""),
            "title": v.get("title", ""),
            "price": v.get("price", 0),
            "mileage": v.get("mileage"),
            "dealer_name": v.get("dealer_name", ""),
            "dealer_phone": v.get("dealer_phone", ""),
            "listing_url": v.get("listing_url", ""),
            "image_urls": v.get("image_urls", []),
            "features": v.get("features", []),
            "condition": v.get("condition", ""),
            "year": v.get("year"),
            "make": v.get("make", ""),
            "model": v.get("model", ""),
        }
        for v in all_vehicles
    ]

    async def event_stream():
        await SessionDocument.find_one(
            SessionDocument.session_id == session_id
        ).update({"$set": {"phase": "calling"}})

        yield _sse_event("start", {
            "total_vehicles": len(vehicles),
            "all_vehicles": vehicles_for_ui,
            "message": f"Calling {len(vehicles)} dealer{'s' if len(vehicles) != 1 else ''}...",
        })

        summaries: dict[str, dict] = {}

        for i, vehicle in enumerate(vehicles):
            vid = vehicle.get("vehicle_id", f"v-{i}")
            title = vehicle.get("title", "vehicle")
            phone = vehicle.get("dealer_phone", "")
            dealer_name = vehicle.get("dealer_name", f"Dealer {i + 1}")
            override = settings.to_number if settings.to_number and not settings.to_number.startswith("+1555") else ""
            call_phone = override or phone

            yield _sse_event("calling", {
                "vehicle_id": vid,
                "dealer_name": dealer_name,
                "title": title,
                "image_urls": vehicle.get("image_urls", []),
                "index": i,
                "total": len(vehicles),
                "message": f"Calling {dealer_name} about {title}...",
            })

            prompt = build_dealer_call_prompt(
                vehicle_title=title,
                listing_price=vehicle.get("price", 0),
                vehicle_year=str(vehicle.get("year", "")),
                vehicle_features=vehicle.get("features", []),
                user_budget_max=preferences.get("price_max", 100_000),
                user_zip=preferences.get("zip_code", ""),
                user_name=user_name,
                financing_interest=preferences.get("finance", "undecided") != "cash",
                trade_in_description=preferences.get("trade_in", ""),
            )
            greeting = build_dealer_call_greeting(title, dealer_name)

            call_resp = await initiate_call(local_url, call_phone, prompt, greeting)
            call_id = call_resp.get("call_id", "")
            transcript_text = ""

            if call_id and call_resp.get("status") != "failed":
                yield _sse_event("call_connected", {
                    "vehicle_id": vid,
                    "call_id": call_id,
                    "message": f"Connected to {dealer_name}. AI agent is talking...",
                })

                result = await poll_for_transcript(local_url, call_id)
                transcript_text = result.get("transcript_text", "")
            else:
                error_detail = call_resp.get("error", "unknown")
                log.error("Call failed for %s: %s", dealer_name, error_detail)
                yield _sse_event("call_failed", {
                    "vehicle_id": vid,
                    "error": error_detail,
                    "message": f"Failed to call {dealer_name}: {error_detail[:120]}",
                })

            yield _sse_event("call_complete", {
                "vehicle_id": vid,
                "dealer_name": dealer_name,
                "has_transcript": bool(transcript_text),
                "transcript_text": transcript_text,
                "message": f"Finished call with {dealer_name}. Summarizing...",
            })

            if transcript_text:
                summary = await _summarize_transcript(vehicle, transcript_text)
            else:
                summary = {
                    "is_available": None,
                    "key_takeaways": "Could not reach dealer -- no transcript.",
                    "recommendation": "needs more info",
                    "condition": {},
                    "pricing": {"listed_price": vehicle.get("price", 0), "best_quoted_price": None, "is_negotiable": False, "out_the_door_price": None},
                    "financing": {"available": False, "apr_range": None},
                    "dealer_impression": {"responsiveness": "unreachable", "willingness_to_deal": "unknown"},
                    "red_flags": [],
                }

            summaries[vid] = summary

            try:
                comm = CommunicationDocument(
                    session_id=session_id,
                    vehicle_id=vid,
                    comm_type="call",
                    status="completed" if transcript_text else "failed",
                    dealer_phone=call_phone,
                    transcript=[{"text": transcript_text}] if transcript_text else [],
                    summary=summary.get("key_takeaways", ""),
                    call_details=summary,
                )
                await comm.insert()
            except Exception as exc:
                log.warning("Failed to persist call record for %s: %s", vid, exc)

            yield _sse_event("summary_ready", {
                "vehicle_id": vid,
                "dealer_name": dealer_name,
                "summary": summary,
                "message": f"Summary ready for {title}.",
            })

        yield _sse_event("ranking", {
            "message": "All calls complete. Ranking vehicles...",
        })

        ranked = _rank_vehicles(vehicles, summaries)
        top3 = ranked[:min(3, len(ranked))]
        top3_results = []
        for rank_idx, v in enumerate(top3):
            vid = v.get("vehicle_id", "")
            s = summaries.get(vid, {})
            top3_results.append({
                "rank": rank_idx + 1,
                "vehicle_id": vid,
                "title": v.get("title", ""),
                "price": v.get("price", 0),
                "mileage": v.get("mileage"),
                "dealer_name": v.get("dealer_name", ""),
                "dealer_phone": v.get("dealer_phone", ""),
                "listing_url": v.get("listing_url", ""),
                "features": v.get("features", []),
                "overall_score": v.get("overall_score", 0),
                "final_score": v.get("_final_score", 0),
                "image_urls": v.get("image_urls", []),
                "call_summary": s,
            })

        await SessionDocument.find_one(
            SessionDocument.session_id == session_id
        ).update({"$set": {"phase": "dashboard"}})

        yield _sse_event("complete", {
            "top3": top3_results,
            "all_summaries": {vid: s for vid, s in summaries.items()},
            "message": "Analysis complete! Here are your top recommendations.",
        })

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
