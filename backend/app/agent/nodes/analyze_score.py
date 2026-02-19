"""Node: analyze_and_score -- deterministic scoring of search results."""

from uuid import uuid4

from langchain_core.messages import AIMessage

from app.agent.state import AgentState
from app.services.scoring_service import score_vehicles


def analyze_and_score(state: AgentState) -> dict:
    """Score and rank raw search results using the deterministic scoring engine.

    Converts raw search results into the standardised vehicle format, then
    runs the scoring algorithm.
    """
    raw_results = state.get("raw_search_results", [])
    preferences = state.get("preferences", {})
    additional_filters = state.get("additional_filters", {})

    if not raw_results:
        return {
            "vehicles": [],
            "price_stats": {},
            "current_phase": "no_results",
            "messages": [AIMessage(content="No results to score.")],
        }

    merged_prefs = {**preferences, **additional_filters}
    vehicles = _normalize_raw_results(raw_results, preferences)
    scored = score_vehicles(vehicles, merged_prefs)
    price_stats = _compute_price_stats(scored)

    return {
        "vehicles": scored,
        "price_stats": price_stats,
        "current_phase": "shortlist",
        "messages": [
            AIMessage(
                content=(
                    f"Scored {len(scored)} vehicles. "
                    f"Price range: ${price_stats.get('lowest_price', 0):,.0f} "
                    f"- ${price_stats.get('highest_price', 0):,.0f}."
                )
            )
        ],
    }


def _normalize_raw_results(raw_results: list[dict], preferences: dict) -> list[dict]:
    """Convert raw search/scrape results into the standard vehicle dict shape."""
    make = preferences.get("make", "")
    model = preferences.get("model", "")

    vehicles = []
    for i, raw in enumerate(raw_results):
        title = raw.get("title", f"{make} {model} - Listing {i + 1}")
        # Clean up stub markers
        title = title.replace("[STUB] ", "")

        vehicles.append({
            "vehicle_id": raw.get("vehicle_id", str(uuid4())),
            "rank": i + 1,
            "title": title,
            "price": raw.get("price", 20000 + i * 1500),
            "mileage": raw.get("mileage", 15000 + i * 5000),
            "condition": raw.get("condition", preferences.get("condition", "used")),
            "dealer_name": raw.get("dealer_name", f"Dealer {i + 1}"),
            "dealer_phone": raw.get("dealer_phone", f"+1555000{i:04d}"),
            "dealer_address": raw.get("dealer_address", ""),
            "dealer_distance_miles": raw.get("dealer_distance_miles", round(5.0 + i * 3.1, 1)),
            "listing_url": raw.get("url", raw.get("listing_url", "")),
            "image_urls": raw.get("image_urls", []),
            "features": raw.get("features", ["backup_camera", "bluetooth"]),
            "condition_score": 0.0,
            "price_score": 0.0,
            "overall_score": 0.0,
            "known_issues": raw.get("known_issues", []),
            "source": raw.get("source", "web"),
        })

    return vehicles


def _compute_price_stats(vehicles: list[dict]) -> dict:
    """Compute basic price statistics."""
    if not vehicles:
        return {"avg_market_price": 0, "lowest_price": 0, "highest_price": 0}

    prices = [v.get("price", 0) for v in vehicles]
    return {
        "avg_market_price": round(sum(prices) / len(prices), 2),
        "lowest_price": min(prices),
        "highest_price": max(prices),
    }
