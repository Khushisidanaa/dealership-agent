"""Pluggable web scraper service for finding vehicle listings."""

import asyncio
from typing import Any

from app.models.documents import SearchResultDocument


async def search_cars(
    requirements: dict,
    dealers: list[Any],
) -> list[dict]:
    """
    Search for cars matching user requirements.
    Returns empty list by default; plug in a scraper when needed.
    """
    return []


async def run_search(
    search_id: str,
    preferences: dict,
    additional_filters: dict,
) -> None:
    """Run the search pipeline in background.

    Steps:
    1. Build search query from preferences + additional_filters
    2. Scrape configured sources
    3. Score and rank results
    4. Persist to MongoDB

    This is a stub -- replace with real scraping logic.
    """
    doc = await SearchResultDocument.find_one(
        SearchResultDocument.search_id == search_id
    )
    if not doc:
        return

    try:
        doc.status = "scraping"
        doc.progress_percent = 10
        await doc.save()

        doc.progress_percent = 50
        await doc.save()

        doc.progress_percent = 80
        doc.status = "analyzing"
        await doc.save()

        await asyncio.sleep(1)

        doc.vehicles = []
        doc.price_stats = _compute_price_stats([])
        doc.status = "completed"
        doc.progress_percent = 100
        await doc.save()

    except Exception:
        doc.status = "failed"
        await doc.save()


def _compute_price_stats(vehicles: list[dict]) -> dict:
    """Compute basic price statistics from vehicle list."""
    if not vehicles:
        return {"avg_market_price": 0, "lowest_price": 0, "highest_price": 0}

    prices = [v["price"] for v in vehicles]
    return {
        "avg_market_price": round(sum(prices) / len(prices), 2),
        "lowest_price": min(prices),
        "highest_price": max(prices),
    }
