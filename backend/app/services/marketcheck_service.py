"""
MarketCheck API service for searching vehicle listings.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple, Union

import httpx

from app.config import get_settings
from app.models.schemas import (
    VehicleListingResult,
    CarfaxInfo,
    ColorInfo,
    DealerInfo,
    BuildInfo,
    MediaInfo,
    PriceStats,
)

logger = logging.getLogger(__name__)

MARKETCHECK_BASE = "https://api.marketcheck.com/v2/search/car/active"


def _safe_int(val: Any) -> Optional[int]:
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def _safe_float(val: Any) -> Optional[float]:
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _listing_to_result(listing: Dict[str, Any], rank: int) -> VehicleListingResult:
    """Map a MarketCheck listing to VehicleListingResult for frontend display."""
    build = listing.get("build") or {}
    dealer = listing.get("dealer") or {}
    media = listing.get("media") or {}

    year = build.get("year") or listing.get("year") or 0
    make = build.get("make") or listing.get("make") or "?"
    model = build.get("model") or listing.get("model") or "?"
    trim = build.get("trim") or ""
    heading = listing.get("heading") or ""
    title = heading or f"{year} {make} {model} {trim}".strip()

    price = _safe_float(listing.get("price"))
    msrp = _safe_float(listing.get("msrp"))
    miles = _safe_int(listing.get("miles"))

    # Dealer
    addr_parts = [
        dealer.get("street"),
        dealer.get("city"),
        dealer.get("state"),
        dealer.get("zip"),
    ]
    full_address = ", ".join(str(p) for p in addr_parts if p)

    dealer_info = DealerInfo(
        id=_safe_int(dealer.get("id")),
        name=dealer.get("name") or "",
        phone=dealer.get("phone") or "",
        website=dealer.get("website") or "",
        dealer_type=dealer.get("dealer_type") or "",
        street=dealer.get("street") or "",
        city=dealer.get("city") or "",
        state=dealer.get("state") or "",
        zip=dealer.get("zip") or "",
        country=dealer.get("country") or "",
        latitude=dealer.get("latitude"),
        longitude=dealer.get("longitude"),
        full_address=full_address,
    )

    # Media
    pl = media.get("photo_links") or []
    plc = media.get("photo_links_cached") or []
    if not isinstance(pl, list):
        pl = []
    if not isinstance(plc, list):
        plc = []
    pl_str = [str(u) for u in pl]
    plc_str = [str(u) for u in plc]
    media_info = MediaInfo(photo_links=pl_str, photo_links_cached=plc_str)
    image_urls = pl_str if pl_str else plc_str

    # Build
    build_info = BuildInfo(
        year=_safe_int(build.get("year") or listing.get("year")),
        make=build.get("make") or listing.get("make") or "",
        model=build.get("model") or listing.get("model") or "",
        trim=build.get("trim") or "",
        version=build.get("version") or "",
        body_type=build.get("body_type") or "",
        vehicle_type=build.get("vehicle_type") or "",
        transmission=build.get("transmission") or "",
        drivetrain=build.get("drivetrain") or "",
        fuel_type=build.get("fuel_type") or "",
        engine=build.get("engine") or "",
        engine_size=_safe_float(build.get("engine_size")),
        doors=_safe_int(build.get("doors")),
        cylinders=_safe_int(build.get("cylinders")),
        std_seating=str(build.get("std_seating") or ""),
        highway_mpg=_safe_int(build.get("highway_mpg")),
        city_mpg=_safe_int(build.get("city_mpg")),
        powertrain_type=build.get("powertrain_type") or "",
        made_in=build.get("made_in") or "",
    )

    return VehicleListingResult(
        vehicle_id=listing.get("id") or "",
        vin=listing.get("vin") or "",
        rank=rank,
        heading=heading,
        title=title,
        price=price,
        msrp=msrp,
        miles=miles,
        stock_no=str(listing.get("stock_no") or ""),
        days_on_market=_safe_int(listing.get("dom")),
        carfax=CarfaxInfo(
            one_owner=bool(listing.get("carfax_1_owner")),
            clean_title=bool(listing.get("carfax_clean_title")),
        ),
        colors=ColorInfo(
            exterior=listing.get("exterior_color") or "",
            interior=listing.get("interior_color") or "",
            exterior_base=listing.get("base_ext_color") or "",
            interior_base=listing.get("base_int_color") or "",
        ),
        seller_type=listing.get("seller_type") or "",
        inventory_type=listing.get("inventory_type") or "used",
        dealer=dealer_info,
        dealer_distance_miles=_safe_float(listing.get("dist")),
        build=build_info,
        media=media_info,
        image_urls=image_urls,
        listing_url=listing.get("vdp_url") or "",
        source=listing.get("source") or "marketcheck",
        in_transit=bool(listing.get("in_transit")),
    )


def _compute_price_stats(
    results: List[VehicleListingResult],
) -> Optional[PriceStats]:
    """Compute price stats from results."""
    prices = [r.price for r in results if r.price is not None and r.price > 0]
    if not prices:
        return None
    return PriceStats(
        avg_market_price=sum(prices) / len(prices),
        lowest_price=min(prices),
        highest_price=max(prices),
    )


async def search_listings(
    make: str,
    model: str,
    *,
    year: Optional[int] = None,
    year_min: Optional[int] = None,
    year_max: Optional[int] = None,
    zip_code: str = "",
    radius_miles: int = 50,
    car_type: str = "used",
    price_min: Optional[int] = None,
    price_max: Optional[int] = None,
    max_mileage: Optional[int] = None,
    rows: int = 20,
) -> Tuple[List[VehicleListingResult], int, Optional[PriceStats]]:
    """
    Search MarketCheck API for vehicle listings.

    Returns:
        (results, total_found, price_stats)
    """
    settings = get_settings()
    api_key = settings.marketcheck_api_key
    if not api_key:
        logger.error("MARKETCHECK_API_KEY not configured")
        return [], 0, None

    params: Dict[str, Union[str, int]] = {
        "api_key": api_key,
        "make": make,
        "model": model,
        "zip": zip_code,
        "radius": radius_miles,
        "car_type": car_type,
        "rows": rows,
    }

    if year is not None:
        params["year"] = year
    elif year_min is not None or year_max is not None:
        if year_min is not None and year_max is not None:
            params["year_range"] = f"{year_min}-{year_max}"
        elif year_min is not None:
            params["year_range"] = f"{year_min}-"
        else:
            params["year_range"] = f"-{year_max}"

    if price_min is not None or price_max is not None:
        if price_min is not None and price_max is not None:
            params["price_range"] = f"{price_min}-{price_max}"
        elif price_min is not None:
            params["price_range"] = f"{price_min}-"
        else:
            params["price_range"] = f"-{price_max}"

    if max_mileage is not None:
        params["miles_range"] = f"0-{max_mileage}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(MARKETCHECK_BASE, params=params)

    resp.raise_for_status()
    data = resp.json()

    total_found = data.get("num_found", 0)
    raw_listings = data.get("listings", [])

    results: List[VehicleListingResult] = []
    for i, listing in enumerate(raw_listings, 1):
        try:
            vr = _listing_to_result(listing, rank=i)
            results.append(vr)
        except Exception as e:
            logger.warning("Skipping listing %s: %s", listing.get("id"), e)

    price_stats = _compute_price_stats(results)

    return results, total_found, price_stats
