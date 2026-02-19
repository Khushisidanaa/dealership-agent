"""Node: final_ranking -- re-ranks vehicles using structured call summaries + LLM."""

from __future__ import annotations

import json

from langchain_core.messages import AIMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.agent.state import AgentState
from app.config import get_settings


RANKING_PROMPT = """\
You are an analytical car-buying advisor. You have the original scored vehicle \
data PLUS structured summaries from phone calls to each dealership. Your job is \
to produce a final top-3 ranking with a brief justification for each pick.

SCORED VEHICLES:
{vehicles_json}

CALL SUMMARIES (structured data from dealer calls):
{summaries_json}

USER PREFERENCES:
{preferences_json}

RANKING CRITERIA (in priority order):
1. Availability -- skip vehicles confirmed as sold
2. Price competitiveness -- compare best quoted price vs listed, factor negotiability
3. Vehicle condition -- accidents, title status, known issues
4. Dealer impression -- helpful vs evasive, willingness to deal
5. Feature match to user preferences
6. Financing options if user needs them
7. Red flags from the call (evasive answers, pressure tactics, hidden fees)
8. Distance from user location
9. Recommendation from call summary ("worth visiting" > "proceed with caution" > "skip")

Respond with ONLY valid JSON:
{{
  "final_top3": [
    {{
      "vehicle_id": "...",
      "rank": 1,
      "justification": "Why this is the top pick based on call data",
      "call_highlights": "Key facts from the dealer call"
    }},
    {{
      "vehicle_id": "...",
      "rank": 2,
      "justification": "...",
      "call_highlights": "..."
    }},
    {{
      "vehicle_id": "...",
      "rank": 3,
      "justification": "...",
      "call_highlights": "..."
    }}
  ]
}}\
"""


def final_ranking(state: AgentState) -> dict:
    """Re-rank the shortlisted vehicles incorporating call summaries."""
    settings = get_settings()
    vehicles = state.get("vehicles", [])
    shortlist_ids = state.get("shortlist_ids", [])
    call_summaries = state.get("call_summaries", [])
    preferences = state.get("preferences", {})

    shortlisted = [v for v in vehicles if v.get("vehicle_id") in shortlist_ids]

    if not shortlisted:
        return {
            "final_top3": [],
            "current_phase": "dashboard",
            "messages": [AIMessage(content="No vehicles to rank.")],
        }

    has_openai = (
        settings.openai_api_key
        and not settings.openai_api_key.startswith("sk-your")
    )

    if has_openai and call_summaries:
        return _llm_ranking(shortlisted, call_summaries, preferences, settings)

    return _stub_ranking(shortlisted, call_summaries)


def _llm_ranking(
    shortlisted: list[dict],
    call_summaries: list[dict],
    preferences: dict,
    settings,
) -> dict:
    """Use the LLM to produce a reasoned final top-3."""
    system_text = RANKING_PROMPT.format(
        vehicles_json=json.dumps(shortlisted, indent=2),
        summaries_json=json.dumps(call_summaries, indent=2),
        preferences_json=json.dumps(preferences, indent=2),
    )

    llm = ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        temperature=0.2,
        model_kwargs={"response_format": {"type": "json_object"}},
    )

    response = llm.invoke([SystemMessage(content=system_text)])

    try:
        parsed = json.loads(response.content)
        top3_data = parsed.get("final_top3", [])
        top3_ids = [entry["vehicle_id"] for entry in top3_data[:3]]
    except (json.JSONDecodeError, KeyError):
        top3_ids = [v["vehicle_id"] for v in shortlisted[:3]]
        top3_data = []

    lines = []
    for entry in top3_data:
        lines.append(
            f"  {entry.get('rank', '?')}. {entry.get('justification', 'N/A')}"
        )
        if entry.get("call_highlights"):
            lines.append(f"     Call: {entry['call_highlights']}")

    summary = "Final top 3 selected" + (
        ":\n" + "\n".join(lines) if lines else "."
    )

    return {
        "final_top3": top3_ids,
        "current_phase": "dashboard",
        "messages": [AIMessage(content=summary)],
    }


def _stub_ranking(shortlisted: list[dict], call_summaries: list[dict]) -> dict:
    """Rank using call summaries deterministically when no LLM is available."""
    summary_lookup = {
        s["vehicle_id"]: s.get("summary", {})
        for s in call_summaries
    }

    scored = []
    for vehicle in shortlisted:
        vid = vehicle.get("vehicle_id")
        base_score = vehicle.get("overall_score", 0)
        summary = summary_lookup.get(vid, {})

        adjustment = 0
        if summary.get("is_available") is False:
            adjustment -= 100
        if summary.get("recommendation") == "worth visiting":
            adjustment += 2
        elif summary.get("recommendation") == "skip":
            adjustment -= 50
        if summary.get("pricing", {}).get("is_negotiable"):
            adjustment += 1
        if summary.get("red_flags"):
            adjustment -= len(summary["red_flags"])
        impression = summary.get("dealer_impression", {})
        if impression.get("responsiveness") == "helpful":
            adjustment += 1
        elif impression.get("responsiveness") == "evasive":
            adjustment -= 2

        scored.append((vehicle, base_score + adjustment, summary))

    scored.sort(key=lambda x: x[1], reverse=True)
    top3 = scored[:3]
    top3_ids = [v["vehicle_id"] for v, _, _ in top3]

    lines = []
    for i, (v, score, summary) in enumerate(top3):
        title = v.get("title", "vehicle")
        takeaway = summary.get("key_takeaways", "")
        rec = summary.get("recommendation", "")
        price_info = summary.get("pricing", {})
        best = price_info.get("best_quoted_price")

        line = f"  {i+1}. {title} (score: {score:.1f})"
        if best:
            line += f" | Best price: ${best:,}"
        if rec:
            line += f" | {rec}"
        lines.append(line)
        if takeaway:
            lines.append(f"     {takeaway}")

    summary_text = "Final top 3 (ranked with call data, stub mode):\n" + "\n".join(lines)

    return {
        "final_top3": top3_ids,
        "current_phase": "dashboard",
        "messages": [AIMessage(content=summary_text)],
    }
