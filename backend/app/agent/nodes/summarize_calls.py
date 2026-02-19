"""Node: summarize_calls -- extracts structured data from dealer call transcripts.

Takes the raw transcripts from contact_dealers and uses an LLM (or stub)
to produce a structured summary per vehicle that the dashboard can display.
"""

from __future__ import annotations

import json
import logging

from langchain_core.messages import AIMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.agent.state import AgentState
from app.agent.prompts.call_summary import build_summary_prompt
from app.config import get_settings

log = logging.getLogger(__name__)

_EMPTY_SUMMARY = {
    "is_available": None,
    "condition": {},
    "pricing": {},
    "financing": {},
    "trade_in": {},
    "logistics": {},
    "dealer_impression": {},
    "red_flags": [],
    "key_takeaways": "",
    "recommendation": "needs more info",
}


def summarize_calls(state: AgentState) -> dict:
    """Summarize each completed call transcript into structured data."""
    settings = get_settings()
    communications = state.get("communications", [])

    completed_calls = [
        c for c in communications
        if c.get("status") == "completed" and c.get("transcript_text")
    ]

    if not completed_calls:
        return {
            "call_summaries": [],
            "current_phase": "final_rank",
            "messages": [AIMessage(content="No completed call transcripts to summarize.")],
        }

    has_openai = (
        settings.openai_api_key
        and not settings.openai_api_key.startswith("sk-your")
    )

    if has_openai:
        summaries = _llm_summarize(completed_calls, settings)
    else:
        summaries = _stub_summarize(completed_calls)

    available_count = sum(
        1 for s in summaries if s.get("summary", {}).get("is_available") is True
    )
    msg = (
        f"Summarized {len(summaries)} dealer calls. "
        f"{available_count} vehicles confirmed available."
    )

    return {
        "call_summaries": summaries,
        "current_phase": "final_rank",
        "messages": [AIMessage(content=msg)],
    }


def _llm_summarize(calls: list[dict], settings) -> list[dict]:
    """Use OpenAI to extract structured data from each transcript."""
    llm = ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        temperature=0.1,
        model_kwargs={"response_format": {"type": "json_object"}},
    )

    summaries = []
    for call in calls:
        prompt_text = build_summary_prompt(
            vehicle_title=call.get("vehicle_title", ""),
            listing_price=call.get("listing_price", 0),
            listing_url=call.get("listing_url", ""),
            transcript_text=call.get("transcript_text", ""),
        )

        try:
            response = llm.invoke([SystemMessage(content=prompt_text)])
            parsed = json.loads(response.content)
        except (json.JSONDecodeError, Exception) as exc:
            log.warning("Failed to parse summary for %s: %s", call.get("vehicle_id"), exc)
            parsed = {**_EMPTY_SUMMARY, "key_takeaways": "Summary extraction failed."}

        summaries.append({
            "vehicle_id": call.get("vehicle_id"),
            "dealer_name": call.get("dealer_name", ""),
            "call_id": call.get("call_id", ""),
            "summary": parsed,
        })

    return summaries


def _stub_summarize(calls: list[dict]) -> list[dict]:
    """Parse stub transcripts deterministically without an LLM."""
    summaries = []

    for call in calls:
        transcript = call.get("transcript_text", "")
        title = call.get("vehicle_title", "vehicle")
        price = call.get("listing_price", 0)

        is_available = "still available" not in transcript.lower() or "sold" not in transcript.lower()
        if "sold yesterday" in transcript.lower() or "unfortunately" in transcript.lower():
            is_available = False

        best_price = None
        is_negotiable = False
        for line in transcript.split("\n"):
            if "could probably do" in line.lower() or "we could do" in line.lower():
                is_negotiable = True
                import re
                prices = re.findall(r'\$[\d,]+', line)
                if prices:
                    best_price = int(prices[0].replace('$', '').replace(',', ''))

        has_financing = "financing" in transcript.lower() or "rates" in transcript.lower()
        has_accident = "accident" in transcript.lower() or "fender" in transcript.lower()

        dealer_vibe = "helpful"
        if "come in this week" in transcript.lower():
            dealer_vibe = "neutral"

        if is_available:
            condition_notes = "Details discussed in call"
            for line in transcript.split("\n"):
                if "clean title" in line.lower() or "owner" in line.lower() or "accident" in line.lower():
                    condition_notes = line.split(": ", 1)[1] if ": " in line else line
                    break

            key_takeaways = (
                f"{title} is available. "
                + (f"Best quoted price: ${best_price:,}. " if best_price else "")
                + (f"Condition: {condition_notes}. " if condition_notes else "")
                + ("Financing available. " if has_financing else "")
                + ("Price is negotiable." if is_negotiable else "Price seems firm.")
            )
            recommendation = "worth visiting"
        else:
            key_takeaways = f"{title} has been sold. Dealer mentioned similar options may be available."
            recommendation = "skip"
            condition_notes = "N/A - vehicle sold"

        summary = {
            "is_available": is_available,
            "condition": {
                "accident_history": "minor - repaired" if has_accident else "none reported",
                "mechanical_issues": "none reported",
                "previous_owners": None,
                "title_status": "clean" if "clean title" in transcript.lower() else None,
                "last_service": None,
                "overall_notes": condition_notes,
            },
            "pricing": {
                "listed_price": price,
                "out_the_door_price": (best_price + 1200) if best_price else None,
                "dealer_fees": "included in out-the-door quote",
                "promotions": None,
                "is_negotiable": is_negotiable,
                "best_quoted_price": best_price,
                "price_notes": "Weekly special pricing mentioned" if is_negotiable else None,
            },
            "financing": {
                "available": has_financing,
                "apr_range": "4.9% - 7.9%" if has_financing else None,
                "pre_approval_possible": None,
                "financing_notes": "Multiple lenders available" if has_financing else None,
            },
            "trade_in": {
                "accepted": None,
                "estimated_value": None,
                "trade_in_notes": None,
            },
            "logistics": {
                "test_drive_available": is_available,
                "hours": "Mon-Sat 9am-7pm" if is_available else None,
                "specific_appointment": None,
            },
            "dealer_impression": {
                "responsiveness": dealer_vibe,
                "willingness_to_deal": "medium" if is_negotiable else "low",
                "professionalism": "high",
            },
            "red_flags": (
                ["Vehicle has minor accident history"] if has_accident else []
            ),
            "key_takeaways": key_takeaways,
            "recommendation": recommendation,
        }

        summaries.append({
            "vehicle_id": call.get("vehicle_id"),
            "dealer_name": call.get("dealer_name", ""),
            "call_id": call.get("call_id", ""),
            "summary": summary,
        })

    return summaries
