"""
Build cars.com shopping results URL from search input.

Matches the structure used on cars.com:
  /shopping/results/?makes[]=MAKE&stock_type=used|new|certified&list_price_min=...&list_price_max=...
  &models[]=make-model&year_min=...&year_max=...&mileage_max=...&zip=...&maximum_distance=...&sort=best_match_desc
"""

import urllib.parse
from typing import Any, Dict, Optional


def _slug(s: str) -> str:
    """Lowercase, strip, replace spaces with hyphens."""
    if not s or not isinstance(s, str):
        return ""
    return s.strip().lower().replace(" ", "-")


def build_cars_com_search_url(
    make: str = "",
    model: str = "",
    *,
    year_min: Optional[int] = None,
    year_max: Optional[int] = None,
    zip_code: str = "",
    radius_miles: int = 50,
    car_type: str = "used",
    price_min: Optional[int] = None,
    price_max: Optional[int] = None,
    max_mileage: Optional[int] = None,
) -> str:
    """
    Build a cars.com /shopping/results/ URL from search parameters.

    make: e.g. "Honda", "Toyota"
    model: e.g. "Civic", "Camry"
    year_min, year_max: model year range
    zip_code: center ZIP for search
    radius_miles: maximum_distance (miles)
    car_type: "used" | "new" | "certified"
    price_min, price_max: USD
    max_mileage: max odometer miles
    """
    base = "https://www.cars.com/shopping/results/"
    make_slug = _slug(make)
    model_slug = _slug(model)
    # cars.com uses make-model for a single model, e.g. honda-civic
    model_value = f"{make_slug}-{model_slug}" if (make_slug and model_slug) else model_slug or make_slug

    params: Dict[str, Any] = {}
    if make_slug:
        params["makes[]"] = make_slug
    if model_value:
        params["models[]"] = model_value
    params["stock_type"] = (car_type or "used").lower()
    if price_min is not None and price_min > 0:
        params["list_price_min"] = price_min
    if price_max is not None and price_max > 0:
        params["list_price_max"] = price_max
    if year_min is not None:
        params["year_min"] = year_min
    if year_max is not None:
        params["year_max"] = year_max
    if max_mileage is not None and max_mileage > 0:
        params["mileage_max"] = max_mileage
    if zip_code:
        params["zip"] = str(zip_code).strip()
    if radius_miles > 0:
        params["maximum_distance"] = radius_miles
    params["sort"] = "best_match_desc"

    query = urllib.parse.urlencode(params, doseq=True)
    return f"{base}?{query}"


def build_cars_com_url_from_input(input_dict: Dict[str, Any]) -> str:
    """Build cars.com URL from the Nova Act input schema (e.g. nova-act-input.json)."""
    return build_cars_com_search_url(
        make=str(input_dict.get("make") or ""),
        model=str(input_dict.get("model") or ""),
        year_min=input_dict.get("year_min"),
        year_max=input_dict.get("year_max"),
        zip_code=str(input_dict.get("zip_code") or ""),
        radius_miles=int(input_dict.get("radius_miles") or 50),
        car_type=str(input_dict.get("car_type") or "used"),
        price_min=input_dict.get("price_min"),
        price_max=input_dict.get("price_max"),
        max_mileage=input_dict.get("max_mileage"),
    )
