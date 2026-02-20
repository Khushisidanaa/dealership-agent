"""API: AI-powered pick of the best 2 cars from search results using requirements + vehicle CSV."""

from __future__ import annotations

import csv
import io
import json
import logging

from fastapi import APIRouter, HTTPException
from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI

from app.api.sessions import get_session_or_404
from app.config import get_settings
from app.models.documents import SearchResultDocument
from app.models.user_requirements import get_user_requirements
from app.utils import parse_json_from_llm

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sessions/{session_id}/recommendations", tags=["recommendations"])

PICK_BEST_TWO_PROMPT = """\
You are a car-buying advisor. Given the user's requirements and a short list of vehicles (CSV: vehicle_id, Make, Model, Year, Price), pick the TWO best matching cars.

USER REQUIREMENTS:
{requirements_json}

VEHICLES (CSV):
{vehicles_csv}

Pick the two vehicles that best match the user's budget, preferred make/model, and other requirements. Use the exact vehicle_id from the first column.

Respond with ONLY valid JSON (no markdown):
{{ "vehicle_ids": ["<vehicle_id_1>", "<vehicle_id_2>"] }}

First vehicle_id = top pick, second = runner-up.\
"""


def _vehicles_to_csv(vehicles: list[dict]) -> str:
    """Build a minimal CSV: vehicle_id, Make, Model, Year, Price."""
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["vehicle_id", "Make", "Model", "Year", "Price"])
    for v in vehicles:
        vid = v.get("vehicle_id") or ""
        make = v.get("make") or ""
        model = v.get("model") or ""
        year = v.get("year") or ""
        price = v.get("price") or 0
        w.writerow([vid, make, model, year, price])
    return out.getvalue().strip()


@router.post("/pick-best-two")
async def pick_best_two(session_id: str):
    """Use requirements + vehicle CSV (Make, Model, Year, Price) to have AI pick the best 2 vehicles."""
    session = await get_session_or_404(session_id)

    # Requirements only (no conversation history)
    prefs = session.preferences or {}
    if session.user_id:
        req = await get_user_requirements(session.user_id)
        if req:
            prefs = req.model_dump()
    requirements_json = json.dumps(prefs, indent=2)

    # Found vehicles (latest search for this session)
    search_doc = await SearchResultDocument.find_one(
        SearchResultDocument.session_id == session_id,
        SearchResultDocument.status == "completed",
    )
    if not search_doc or not search_doc.vehicles:
        raise HTTPException(
            status_code=400,
            detail="No search results found. Run a search first.",
        )
    vehicles = search_doc.vehicles
    vehicles_csv = _vehicles_to_csv(vehicles)

    settings = get_settings()
    key = (settings.openai_api_key or "").strip()
    has_openai = bool(key and not key.startswith("sk-your"))

    if not has_openai:
        # Stub: return first 2 by rank
        top2 = sorted(vehicles, key=lambda v: v.get("rank", 999))[:2]
        return {"vehicle_ids": [v.get("vehicle_id", "") for v in top2 if v.get("vehicle_id")]}

    system_text = PICK_BEST_TWO_PROMPT.format(
        requirements_json=requirements_json,
        vehicles_csv=vehicles_csv,
    )

    try:
        llm = ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=0.2,
        )
        response = llm.invoke([SystemMessage(content=system_text)])
        parsed = parse_json_from_llm(response.content)
        raw_ids = parsed.get("vehicle_ids") or []
        # Ensure we only return IDs that exist in our list
        valid_ids = {v.get("vehicle_id") for v in vehicles if v.get("vehicle_id")}
        vehicle_ids = [vid for vid in raw_ids[:2] if vid in valid_ids]
        # If LLM returned invalid or fewer than 2, fill with top by rank
        if len(vehicle_ids) < 2:
            for v in sorted(vehicles, key=lambda x: x.get("rank", 999)):
                vid = v.get("vehicle_id")
                if vid and vid not in vehicle_ids:
                    vehicle_ids.append(vid)
                    if len(vehicle_ids) >= 2:
                        break
        return {"vehicle_ids": vehicle_ids[:2]}
    except (json.JSONDecodeError, ValueError, KeyError) as e:
        log.warning("Pick-best-two LLM parse failed: %s", e)
        top2 = sorted(vehicles, key=lambda v: v.get("rank", 999))[:2]
        return {"vehicle_ids": [v.get("vehicle_id", "") for v in top2 if v.get("vehicle_id")]}
