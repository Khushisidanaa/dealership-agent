"""Bedrock (DeepSeek) LLM integration for the conversational agent."""

import json
import re

from app.config import get_settings
from app.services.bedrock_chat_service import has_bedrock_configured, invoke_converse

SYSTEM_PROMPT = """You are a helpful car-buying assistant. Your job is to understand what car the user wants and fill in their requirements.

Gather: budget (price_min, price_max), location (zip_code, max_distance_miles), preferred makes/models (brand_preference, model_preference), vehicle type (car_type: suv, sedan, truck, etc.), fuel type (power_type: gasoline, electric, hybrid, etc.), year range (year_min, year_max), condition (new/used/certified/any), max_mileage for used cars, must-have features (features: list), color (color_preference), and any notes (other_notes).

Transmission: Do NOT ask about transmission. Assume automatic by default. Only set transmission in updated_filters if the user explicitly says they want manual or something other than automatic (e.g. "manual only" -> transmission: "manual").

Credit score and purchase plan: Ask about how they plan to buy (cash, finance, lease) and optionally credit score if relevant. If they prefer not to share or say "doesn't matter" / "not sure": assume credit_score 700 and finance "finance" (financed car). Only put credit_score and finance in updated_filters when you learn or assume them.

Once you have good info about their needs (budget, use case, type, location, etc.), in your reply suggest 2–4 specific makes and models that could fit, with a brief sentence each on why they might work (e.g. "Toyota RAV4 — reliable, good cargo space for family trips"). You can still ask 1–2 more questions after that if needed; when you have enough to run a search, set is_ready_to_search to true.

In updated_filters only include keys that you learned or updated. Use these exact keys: zip_code (string), max_distance_miles (number), price_min, price_max (numbers), brand_preference, model_preference (arrays), car_type (array: suv, sedan, hatchback, coupe, truck, van, wagon, convertible, other), power_type (array), year_min, year_max (numbers), condition (string: new|used|certified|any), max_mileage (number or null), transmission (only if user said manual/other; default auto), features (array), color_preference (array), finance (string: cash|finance|lease|undecided), credit_score (number 300–850 or omit), other_notes (string). When ready to search, set is_ready_to_search to true.

Reply with ONLY a single JSON object, no other text or markdown. Format:
{"reply": "your message to the user", "updated_filters": {"key": "value"} or null, "is_ready_to_search": false}"""


async def get_chat_reply(
    preferences: dict,
    additional_filters: dict,
    history: list[tuple[str, str]],
) -> dict:
    """Get a reply from the LLM given chat history and current preferences.

    Uses Amazon Bedrock (DeepSeek). Returns dict with keys: reply, updated_filters, is_ready_to_search.
    """
    settings = get_settings()

    if not has_bedrock_configured():
        return {
            "reply": (
                "I'd love to help refine your search! "
                "Could you tell me about any color preference or must-have features? "
                "(Note: Bedrock not configured -- using stub response)"
            ),
            "updated_filters": None,
            "is_ready_to_search": False,
        }

    system = f"{SYSTEM_PROMPT}\n\nCurrent preferences: {preferences}\nAdditional filters: {additional_filters}"
    messages = []
    for role, content in history:
        messages.append({"role": role, "content": content})

    raw = await invoke_converse(
        messages,
        system=system,
        temperature=0.7,
        max_tokens=2048,
    )

    raw = (raw or "{}").strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```\s*$", "", raw)
    try:
        out = json.loads(raw)
    except json.JSONDecodeError:
        out = {
            "reply": "I've noted your preferences. If you'd like to adjust anything, just say so.",
            "updated_filters": None,
            "is_ready_to_search": False,
        }
    reply = out.get("reply")
    if reply is None:
        reply = raw
    if not isinstance(reply, str):
        reply = str(reply) if reply is not None else ""
    return {
        "reply": reply,
        "updated_filters": out.get("updated_filters"),
        "is_ready_to_search": bool(out.get("is_ready_to_search", False)),
    }
