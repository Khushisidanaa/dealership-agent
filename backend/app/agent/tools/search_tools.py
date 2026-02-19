"""Web search and listing scraper tools for the LangGraph agent."""

import asyncio
from uuid import uuid4

from langchain_core.tools import tool

from app.config import get_settings


@tool
def search_you_com(query: str, count: int = 10) -> list[dict]:
    """Search the web for car listings using the you.com Search API.

    Args:
        query: Search query string (e.g. '2023 Toyota Camry used Los Angeles').
        count: Number of results to return (1-20).

    Returns:
        List of search result dicts with keys: title, url, snippet.
    """
    settings = get_settings()

    if not settings.openai_api_key or settings.openai_api_key.startswith("sk-your"):
        return _stub_search_results(query, count)

    try:
        from youdotcom import You
        client = You(settings.openai_api_key)
        raw = client.search.unified(query=query, count=min(count, 20))

        results = []
        for hit in (raw.get("hits") or raw.get("results") or [])[:count]:
            results.append({
                "title": hit.get("title", ""),
                "url": hit.get("url", ""),
                "snippet": hit.get("description", hit.get("snippet", "")),
            })
        return results

    except Exception:
        return _stub_search_results(query, count)


@tool
def scrape_listing(url: str) -> dict:
    """Scrape detailed vehicle information from a listing URL.

    Args:
        url: The full URL of the vehicle listing page.

    Returns:
        Dict with vehicle details: title, price, mileage, dealer info, features, etc.
    """
    if not url or url.startswith("[STUB]"):
        return _stub_vehicle_detail()

    try:
        import httpx
        from bs4 import BeautifulSoup

        resp = httpx.get(url, timeout=15, follow_redirects=True)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        title = soup.title.string.strip() if soup.title else "Unknown Vehicle"
        return {
            "vehicle_id": str(uuid4()),
            "title": title,
            "price": 0,
            "mileage": 0,
            "listing_url": url,
            "raw_text": soup.get_text(" ", strip=True)[:2000],
            "source": "scraped",
        }

    except Exception:
        return _stub_vehicle_detail()


def _stub_search_results(query: str, count: int) -> list[dict]:
    """Generate stub search results when API is unavailable."""
    return [
        {
            "title": f"[STUB] {query} - Result {i + 1}",
            "url": f"https://example.com/listing/{uuid4()}",
            "snippet": f"Stub result {i + 1} for query: {query}",
        }
        for i in range(min(count, 5))
    ]


def _stub_vehicle_detail() -> dict:
    """Generate a stub vehicle detail when scraping fails."""
    return {
        "vehicle_id": str(uuid4()),
        "title": "[STUB] Vehicle Detail",
        "price": 25000,
        "mileage": 30000,
        "listing_url": "",
        "raw_text": "Stub vehicle detail -- replace with real scraping.",
        "source": "stub",
    }


SEARCH_TOOLS = [search_you_com, scrape_listing]
