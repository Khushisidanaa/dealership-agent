"""Node: web_search -- searches the web for vehicle listings using tools."""

import json
from uuid import uuid4

from langchain_core.messages import AIMessage

from app.agent.state import AgentState
from app.agent.tools.search_tools import search_you_com, scrape_listing


def _build_search_queries(preferences: dict, additional_filters: dict) -> list[str]:
    """Build search queries from preferences and filters."""
    make = preferences.get("make", "")
    model = preferences.get("model", "")
    year_min = preferences.get("year_min", "")
    year_max = preferences.get("year_max", "")
    zip_code = preferences.get("zip_code", "")
    condition = preferences.get("condition", "any")
    price_max = preferences.get("price_max", "")

    color = additional_filters.get("color", "")
    fuel_type = additional_filters.get("fuel_type", "")

    base = f"{make} {model}".strip()
    year_part = f"{year_min}-{year_max}" if year_min and year_max else ""
    condition_part = condition if condition != "any" else ""

    queries = []

    primary = f"{year_part} {base} {condition_part} for sale near {zip_code}".strip()
    if price_max:
        primary += f" under ${price_max}"
    queries.append(primary)

    if color:
        queries.append(f"{year_part} {base} {color} for sale near {zip_code}".strip())

    if fuel_type and fuel_type != "any":
        queries.append(f"{year_part} {base} {fuel_type} for sale near {zip_code}".strip())

    return queries


def web_search(state: AgentState) -> dict:
    """Execute web searches and collect raw results."""
    preferences = state.get("preferences", {})
    additional_filters = state.get("additional_filters", {})
    retry_count = state.get("retry_count", 0)

    queries = _build_search_queries(preferences, additional_filters)

    all_results: list[dict] = []
    for query in queries:
        results = search_you_com.invoke({"query": query, "count": 10})
        if isinstance(results, list):
            all_results.extend(results)

    # Deduplicate by URL
    seen_urls: set[str] = set()
    unique_results: list[dict] = []
    for r in all_results:
        url = r.get("url", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique_results.append(r)

    has_results = len(unique_results) > 0

    if not has_results and retry_count < 2:
        return {
            "search_queries": queries,
            "raw_search_results": [],
            "retry_count": retry_count + 1,
            "current_phase": "search",
            "messages": [
                AIMessage(content=f"No results found. Retrying with broader query (attempt {retry_count + 2}).")
            ],
        }

    return {
        "search_queries": queries,
        "raw_search_results": unique_results,
        "current_phase": "analyze" if has_results else "no_results",
        "retry_count": 0,
        "messages": [
            AIMessage(content=f"Found {len(unique_results)} raw listings from web search.")
        ],
    }
