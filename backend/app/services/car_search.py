"""
Unified car search: Nova Act (with cache) or MarketCheck, with fallback.
"""

import logging
from typing import Optional, Tuple

from app.config import get_settings
from app.models.schemas import PriceStats, VehicleListingResult
from app.services.marketcheck_service import search_listings as marketcheck_search_listings
from app.services.nova_act_service import has_nova_act_configured, search_listings_nova_act

log = logging.getLogger(__name__)


def _effective_provider(settings) -> str:
    """Use nova_act when configured and provider not set; else use explicit provider or marketcheck."""
    provider = (settings.car_search_provider or "").strip().lower()
    if provider:
        return provider
    # No explicit provider: use Nova Act if configured (AWS creds or Nova Act API key), else MarketCheck
    if has_nova_act_configured():
        return "nova_act"
    return "marketcheck"


async def search_listings(
    make: str = "",
    model: str = "",
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
) -> Tuple[list[VehicleListingResult], int, Optional[PriceStats]]:
    """
    Search vehicle listings. Uses CAR_SEARCH_PROVIDER (nova_act | marketcheck).
    When provider is nova_act, results are cached to stay within rate limits (5000 RPD).
    Falls back to MarketCheck if Nova Act returns no results and MarketCheck is configured.
    """
    settings = get_settings()
    provider = _effective_provider(settings)
    use_nova = provider == "nova_act"

    if use_nova and has_nova_act_configured():
        log.info(
            "Car search: provider=nova_act — invoking Nova Act (real cars.com data when API key set). make=%s model=%s zip=%s",
            make,
            model,
            zip_code,
        )
        # Cap rows for Nova to reduce API usage
        nova_rows = min(rows, 10)
        try:
            results, total, price_stats = await search_listings_nova_act(
                make=make,
                model=model,
                year_min=year_min,
                year_max=year_max,
                zip_code=zip_code,
                radius_miles=radius_miles,
                car_type=car_type,
                price_min=price_min,
                price_max=price_max,
                max_mileage=max_mileage,
                rows=nova_rows,
            )
            # Only fall back to MarketCheck if user explicitly set provider to marketcheck (don't when we defaulted to nova_act)
            explicitly_marketcheck = (settings.car_search_provider or "").strip().lower() == "marketcheck"
            if results or not explicitly_marketcheck or not settings.marketcheck_api_key:
                return results, total, price_stats
            log.info("Nova Act returned no results; falling back to MarketCheck")
        except Exception as exc:
            log.warning("Nova Act search failed: %s", exc)
            if (settings.car_search_provider or "").strip().lower() != "marketcheck" or not settings.marketcheck_api_key:
                return [], 0, None
            log.info("Falling back to MarketCheck")

    return await marketcheck_search_listings(
        make=make,
        model=model,
        year=year,
        year_min=year_min,
        year_max=year_max,
        zip_code=zip_code,
        radius_miles=radius_miles,
        car_type=car_type,
        price_min=price_min,
        price_max=price_max,
        max_mileage=max_mileage,
        rows=rows,
    )
