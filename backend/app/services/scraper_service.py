"""Pluggable web scraper service for finding vehicle listings."""

import asyncio
from uuid import uuid4

from app.models.documents import SearchResultDocument


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

        # TODO: replace with real scraper calls
        await asyncio.sleep(2)  # simulate network delay

        doc.progress_percent = 50
        await doc.save()

        # Stub: generate mock vehicles
        stub_vehicles = _generate_stub_vehicles(preferences)

        doc.progress_percent = 80
        doc.status = "analyzing"
        await doc.save()

        await asyncio.sleep(1)  # simulate scoring

        doc.vehicles = stub_vehicles
        doc.price_stats = _compute_price_stats(stub_vehicles)
        doc.status = "completed"
        doc.progress_percent = 100
        await doc.save()

    except Exception:
        doc.status = "failed"
        await doc.save()


def _generate_stub_vehicles(preferences: dict) -> list[dict]:
    """Generate placeholder vehicles for development. Replace with real scraping."""
    make = preferences.get("make", "Toyota")
    model = preferences.get("model", "Camry")

    vehicles = []
    for i in range(5):
        vehicles.append({
            "vehicle_id": str(uuid4()),
            "rank": i + 1,
            "title": f"2023 {make} {model} - Listing {i + 1}",
            "price": 22000 + (i * 1500),
            "mileage": 15000 + (i * 5000),
            "condition": "used",
            "dealer_name": f"Demo Dealer {i + 1}",
            "dealer_phone": f"+1555000000{i}",
            "dealer_address": f"{100 + i} Main St, Los Angeles, CA",
            "dealer_distance_miles": round(5.0 + i * 3.2, 1),
            "listing_url": "",
            "image_urls": [],
            "features": ["backup_camera", "bluetooth"],
            "condition_score": round(9.0 - i * 0.3, 1),
            "price_score": round(9.5 - i * 0.5, 1),
            "overall_score": round(9.2 - i * 0.4, 1),
            "known_issues": [],
            "source": "stub",
        })
    return vehicles


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
