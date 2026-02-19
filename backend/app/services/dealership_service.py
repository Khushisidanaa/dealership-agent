"""
Discover dealerships in an area (Google Maps: Geocoding + Places API).
If GOOGLE_MAPS_API_KEY is set, uses real APIs; otherwise falls back to stub data.
"""
import logging
from typing import Optional, Tuple

import httpx

from app.config import get_settings
from app.models.documents import DealershipDocument, utc_now

logger = logging.getLogger(__name__)

# Places API max radius in meters; 50 miles ≈ 80,467 m
MAX_RADIUS_METERS = 50_000.0


async def _geocode_zip(zip_code: str) -> Optional[Tuple[float, float]]:
    """Convert zip code to (lat, lng) using Google Geocoding API."""
    settings = get_settings()
    if not settings.google_maps_api_key:
        return None
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {"address": zip_code, "key": settings.google_maps_api_key}
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
    if data.get("status") != "OK" or not data.get("results"):
        return None
    loc = data["results"][0]["geometry"]["location"]
    return (loc["lat"], loc["lng"])


async def _places_search_nearby(lat: float, lng: float, radius_meters: float) -> list[dict]:
    """Search for car_dealer places near (lat, lng) using Places API (New) searchNearby."""
    settings = get_settings()
    if not settings.google_maps_api_key:
        return []
    # maxResultCount 1–20; radius 0–50000 meters
    radius_meters = min(max(0, radius_meters), MAX_RADIUS_METERS)
    url = "https://places.googleapis.com/v1/places:searchNearby"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": settings.google_maps_api_key,
        "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,places.internationalPhoneNumber,places.nationalPhoneNumber,places.websiteUri,places.location,places.rating,places.types",
    }
    body = {
        "includedTypes": ["car_dealer"],
        "maxResultCount": 20,
        "locationRestriction": {
            "circle": {
                "center": {"latitude": lat, "longitude": lng},
                "radius": radius_meters,
            }
        },
        "rankPreference": "DISTANCE",
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(url, json=body, headers=headers)
        if resp.status_code != 200:
            logger.warning("Places API error: %s %s", resp.status_code, resp.text[:200])
            return []
        data = resp.json()
    places = data.get("places") or []
    out = []
    for p in places:
        place_id = p.get("id") or (p.get("name", "").replace("places/", "") if p.get("name") else "")
        if not place_id:
            continue
        display = p.get("displayName") or {}
        name = display.get("text", "") if isinstance(display, dict) else str(display)
        loc = p.get("location") or {}
        lat_val = loc.get("latitude")
        lng_val = loc.get("longitude")
        phone = p.get("internationalPhoneNumber") or p.get("nationalPhoneNumber") or ""
        out.append({
            "dealer_id": place_id,
            "name": name,
            "address": p.get("formattedAddress") or "",
            "phone": phone,
            "website": p.get("websiteUri") or "",
            "lat": lat_val,
            "lng": lng_val,
            "rating": p.get("rating"),
            "types": p.get("types") or ["car_dealer"],
            "raw": p,
        })
    return out


async def discover_dealerships(
    zip_code: str,
    radius_miles: int = 50,
    *,
    source: str = "google_maps",
) -> list[dict]:
    """
    Find dealerships in the area: geocode zip → Places API car_dealer nearby → upsert into DB.
    If GOOGLE_MAPS_API_KEY is set, uses real Google APIs (up to 20 results per request).
    Otherwise returns stub data.
    """
    settings = get_settings()
    if settings.google_maps_api_key:
        coords = await _geocode_zip(zip_code)
        if coords:
            lat, lng = coords
            radius_meters = min(radius_miles * 1609.34, MAX_RADIUS_METERS)
            api_list = await _places_search_nearby(lat, lng, radius_meters)
            if api_list:
                raw_list = api_list
            else:
                raw_list = _stub_dealers_for_zip(zip_code, radius_miles)
        else:
            raw_list = _stub_dealers_for_zip(zip_code, radius_miles)
    else:
        raw_list = _stub_dealers_for_zip(zip_code, radius_miles)
    out = []
    for d in raw_list:
        existing = await DealershipDocument.find_one(
            DealershipDocument.dealer_id == d["dealer_id"]
        )
        if existing:
            existing.name = d["name"]
            existing.address = d["address"]
            existing.phone = d["phone"]
            existing.website = d["website"]
            existing.lat = d.get("lat")
            existing.lng = d.get("lng")
            existing.source = source
            existing.rating = d.get("rating")
            existing.types = d.get("types", [])
            existing.raw = d.get("raw")
            existing.updated_at = utc_now()
            await existing.save()
            out.append(_doc_to_dict(existing))
        else:
            doc = DealershipDocument(
                dealer_id=d["dealer_id"],
                name=d["name"],
                address=d["address"],
                phone=d["phone"],
                website=d["website"],
                lat=d.get("lat"),
                lng=d.get("lng"),
                source=source,
                rating=d.get("rating"),
                types=d.get("types", []),
                raw=d.get("raw"),
            )
            await doc.insert()
            out.append(_doc_to_dict(doc))
    return out


def _doc_to_dict(d: DealershipDocument) -> dict:
    return {
        "dealer_id": d.dealer_id,
        "name": d.name,
        "address": d.address,
        "phone": d.phone,
        "website": d.website,
        "lat": d.lat,
        "lng": d.lng,
        "source": d.source,
        "rating": d.rating,
        "types": d.types,
    }


def _stub_dealers_for_zip(zip_code: str, radius_miles: int) -> list[dict]:
    """
    Stub: return mock dealers for testing. We always return the same N mock entries
    per zip so the UI has something to show. For real 50+ dealerships in 50 miles,
    replace this with a call to Google Places API (or Apple MapKit) using zip + radius.
    """
    # Generate more stub entries so the list feels realistic until Maps API is wired
    names = [
        "Acme Toyota", "Best Honda", "Summit Ford", "Valley Chevrolet", "Mountain Nissan",
        "Canyon Hyundai", "Desert Kia", "Peak Mazda", "Ridge Subaru", "Lake Volkswagen",
        "Metro Dodge", "Central Jeep", "North Chrysler", "South BMW", "East Mercedes",
    ]
    streets = ["Main St", "Oak Ave", "Auto Row", "Dealer Dr", "Car Plaza", "Motor Way"]
    out = []
    for i, name in enumerate(names):
        street = streets[i % len(streets)]
        num = 100 + (i * 50)
        out.append({
            "dealer_id": f"stub_place_{zip_code}_{i + 1}",
            "name": name,
            "address": f"{num} {street}, Zip {zip_code}",
            "phone": f"+1555{i:07d}"[:12],
            "website": f"https://dealer{i + 1}.example.com",
            "lat": 40.5 + (i * 0.01),
            "lng": -111.9 + (i * 0.01),
            "rating": round(3.5 + (i % 5) * 0.2, 1),
            "types": ["car_dealer", "point_of_interest"],
            "raw": None,
        })
    return out


async def get_dealerships_in_area(
    zip_code: str,
    radius_miles: int = 50,
) -> list[DealershipDocument]:
    """
    Return dealerships already in DB that are in the given area.
    Stub: no real geo filter; either run discover_dealerships first or we return all.
    TODO: geocode zip, filter by lat/lng distance.
    """
    # For now return all; later filter by distance from zip centroid
    cursor = DealershipDocument.find({}).limit(100)
    return await cursor.to_list(length=100)
