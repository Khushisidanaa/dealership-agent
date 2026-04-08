"""
Nova Act car search service (real data only).

Uses (1) Nova Act SDK browser (cars.com) when API key is set, or (2) Nova Act
workflow when deployed (S3 results). No synthetic/hallucinated listings.
Supports Nova Act API key (AWS_NOVA_HACKATHON_API_KEY or NOVA_ACT_API_KEY) from
nova.amazon.com/dev. Includes in-memory cache (30 min TTL) for rate limits.

Requests per search (uncached):
- Browser path: cars.com URL, N listing page loads, parse HTML to VehicleListingResult.
- Workflow path: create_workflow_run + poll + S3.
Cache hits: 0 external requests.
"""

import asyncio
import json
import logging
import os
import time
import urllib.parse
from typing import Any, Dict, List, Optional, Tuple

from app.config import get_settings
from app.models.schemas import (
    BuildInfo,
    DealerInfo,
    MediaInfo,
    PriceStats,
    VehicleListingResult,
)
from app.services.cars_com_parser import parse_cars_com_listing_html
from app.services.cars_com_url import build_cars_com_search_url

logger = logging.getLogger(__name__)

# Cache: 30 min TTL, max 100 entries to stay within 5000 RPD
_CACHE_TTL_SEC = 30 * 60
_CACHE_MAX_SIZE = 100
_cache: Dict[Tuple, Tuple[float, List[VehicleListingResult], int, Optional[PriceStats]]] = {}
_cache_lock = asyncio.Lock()


def _cache_key(
    zip_code: str,
    make: str,
    model: str,
    year_min: Optional[int],
    year_max: Optional[int],
    price_min: Optional[int],
    price_max: Optional[int],
    max_mileage: Optional[int],
    condition: str,
) -> Tuple:
    return (
        zip_code or "",
        make or "",
        model or "",
        year_min,
        year_max,
        price_min,
        price_max,
        max_mileage,
        (condition or "used").lower(),
    )


def _get_aws_credentials() -> Tuple[str, str]:
    """Return (access_key_id, secret_access_key), with fallback to ACCESS_KEY / SECRET_ACCRESS_KEY."""
    s = get_settings()
    ak = (s.aws_access_key_id or "").strip()
    sk = (s.aws_secret_access_key or "").strip()
    if not ak:
        ak = (os.environ.get("ACCESS_KEY") or "").strip()
    if not sk:
        sk = (os.environ.get("SECRET_ACCRESS_KEY") or "").strip()
    return ak, sk


def _get_nova_act_api_key() -> str:
    """Nova Act API key (hackathon); never log this value. Reads config or env NOVA_ACT_API_KEY."""
    key = (get_settings().aws_nova_hackathon_api_key or "").strip()
    if not key:
        key = (os.environ.get("NOVA_ACT_API_KEY") or "").strip()
    return key


def has_nova_act_configured() -> bool:
    """True if Nova Act car search can be used (AWS credentials or Nova Act API key)."""
    ak, sk = _get_aws_credentials()
    if ak and sk:
        return True
    return bool(_get_nova_act_api_key())


def _ensure_nova_act_api_key_env() -> None:
    """Set NOVA_ACT_API_KEY from config so Nova Act SDK/tools can use it (per nova.amazon.com docs)."""
    key = _get_nova_act_api_key()
    if key:
        os.environ["NOVA_ACT_API_KEY"] = key


def _placeholder_image_url(title: str, year: Optional[int], make: str, model: str) -> str:
    """Return a data URI for an SVG placeholder showing the vehicle (so every listing has an image)."""
    if not title or not title.strip():
        label = f"{year or ''} {make or ''} {model or ''}".strip() or "Vehicle"
    else:
        label = title.strip()
    # Keep label short for SVG (truncate, escape for XML)
    label = (label[:40] + "…") if len(label) > 40 else label
    escaped = label.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="400" height="260" viewBox="0 0 400 260">'
        f'<rect width="400" height="260" fill="#0f172a"/>'
        f'<text x="200" y="130" text-anchor="middle" dominant-baseline="middle" '
        f'fill="#94a3b8" font-size="18" font-family="system-ui,sans-serif">{escaped}</text>'
        f"</svg>"
    )
    return "data:image/svg+xml," + urllib.parse.quote(svg, safe="")

def _parse_listings_to_results(items: List[Dict[str, Any]]) -> List[VehicleListingResult]:
    """Map list of dicts (title, price, mileage, dealer_name, ...) to VehicleListingResult."""
    results: List[VehicleListingResult] = []
    for i, row in enumerate(items):
        if not isinstance(row, dict):
            continue
        try:
            title = str(row.get("title") or row.get("heading") or "Unknown Vehicle").strip()
            price = None
            if "price" in row and row["price"] is not None:
                try:
                    price = float(row["price"])
                except (TypeError, ValueError):
                    pass
            miles = None
            if "mileage" in row and row["mileage"] is not None:
                try:
                    miles = int(row["mileage"])
                except (TypeError, ValueError):
                    pass
            dealer_name = str(row.get("dealer_name") or "").strip()
            dealer_phone = str(row.get("dealer_phone") or "").strip()
            dealer_address = str(row.get("dealer_address") or "").strip()
            year = None
            if "year" in row and row["year"] is not None:
                try:
                    year = int(row["year"])
                except (TypeError, ValueError):
                    pass
            make = str(row.get("make") or "").strip()
            model = str(row.get("model") or "").strip()
            listing_url = str(row.get("listing_url") or "").strip()
            # Image: single image_url or list image_urls -> media.photo_links + image_urls
            image_url = str(row.get("image_url") or "").strip()
            image_urls_raw = row.get("image_urls")
            if isinstance(image_urls_raw, list):
                image_urls = [str(u).strip() for u in image_urls_raw if u]
            elif image_url:
                image_urls = [image_url]
            else:
                image_urls = []
            # If no image from LLM, use a placeholder SVG so the card always has an image
            if not image_urls:
                image_urls = [_placeholder_image_url(title, year, make, model)]
            vehicle_id = str(row.get("vehicle_id") or f"nova-{i + 1}")
            logger.info(
                "Nova Act listing image_urls vehicle_id=%s title=%s count=%s urls=%s",
                vehicle_id,
                (title or "")[:50],
                len(image_urls),
                [str(u)[:120] + ("…" if len(str(u)) > 120 else "") for u in image_urls],
            )
            media = MediaInfo(photo_links=image_urls, photo_links_cached=[])

            dealer = DealerInfo(
                name=dealer_name,
                phone=dealer_phone,
                full_address=dealer_address,
            )
            build = BuildInfo(
                year=year,
                make=make,
                model=model,
                transmission=str(row.get("transmission") or "").strip(),
                drivetrain=str(row.get("drivetrain") or "").strip(),
                fuel_type=str(row.get("fuel_type") or "").strip(),
                engine=str(row.get("engine") or "").strip(),
            )
            inv_type = str(row.get("inventory_type") or row.get("condition") or "used").strip().lower()
            if inv_type not in ("new", "used", "certified"):
                inv_type = "used"
            results.append(
                VehicleListingResult(
                    vehicle_id=str(row.get("vehicle_id") or f"nova-{i + 1}"),
                    rank=int(row.get("rank") or i + 1),
                    heading=title,
                    title=title,
                    price=price,
                    miles=miles,
                    vin=str(row.get("vin") or "").strip(),
                    dealer=dealer,
                    build=build,
                    media=media,
                    image_urls=image_urls,
                    listing_url=listing_url,
                    source="nova_act",
                    inventory_type=inv_type,
                )
            )
        except Exception as e:
            logger.warning("Skip listing row %s: %s", i, e)
    return results


def _compute_price_stats(results: List[VehicleListingResult]) -> Optional[PriceStats]:
    prices = [r.price for r in results if r.price is not None and r.price > 0]
    if not prices:
        return None
    return PriceStats(
        avg_market_price=sum(prices) / len(prices),
        lowest_price=min(prices),
        highest_price=max(prices),
    )


def _ordinal(n: int) -> str:
    """1 -> '1st', 2 -> '2nd', etc."""
    if n == 1:
        return "1st"
    if n == 2:
        return "2nd"
    if n == 3:
        return "3rd"
    return f"{n}th"


def _run_nova_act_browser_sync(
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
    num_listings: int = 5,
    api_key: str = "",
) -> List[Dict[str, Any]]:
    """
    Run Nova Act SDK against cars.com: build URL, open results, click first
    num_listings vehicle links, get each VDP HTML, parse to listing dicts.
    Same flow as scripts/run_nova_act_cars.py. Returns list of dicts for _parse_listings_to_results.
    """
    logger.info(
        "Nova Act browser: _run_nova_act_browser_sync ENTERED. Search terms: make=%s model=%s zip=%s radius=%s year_min=%s year_max=%s car_type=%s price_min=%s price_max=%s max_mileage=%s num_listings=%d",
        make,
        model,
        zip_code,
        radius_miles,
        year_min,
        year_max,
        car_type,
        price_min,
        price_max,
        max_mileage,
        num_listings,
    )
    if not api_key:
        logger.warning("Nova Act browser: no API key; skipping (set AWS_NOVA_HACKATHON_API_KEY or NOVA_ACT_API_KEY)")
        return []

    search_url = build_cars_com_search_url(
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
    )
    logger.info(
        "Nova Act browser: built cars.com URL with search terms -> %s (num_listings=%d). Opening Nova Act SDK...",
        search_url,
        num_listings,
    )

    try:
        from nova_act import NovaAct
    except ImportError:
        logger.error("Nova Act SDK not installed. Run: pip install nova-act")
        return []

    os.environ["NOVA_ACT_API_KEY"] = api_key
    parsed_list: List[Dict[str, Any]] = []

    try:
        logger.info("Nova Act browser: NovaAct(starting_page=%s) context manager starting (browser will open)...", search_url[:80])
        with NovaAct(
            starting_page=search_url,
            nova_act_api_key=api_key,
            ignore_https_errors=True,
        ) as nova:
            for i in range(1, num_listings + 1):
                logger.info("Nova Act browser: fetching listing %d/%d", i, num_listings)
                try:
                    nova.act(
                        f"Find and click on the {_ordinal(i)} vehicle listing link in the search results. "
                        f"If the {_ordinal(i)} listing is not visible on the screen, scroll down the results page until you can see it, then click it. "
                        "Click only the link that opens that specific vehicle's detail page. "
                        "Wait for the listing detail page to load."
                    )
                    listing_url = getattr(nova.page, "url", None) or ""
                    if callable(getattr(nova.page, "content", None)):
                        content = nova.page.content() or ""
                    else:
                        content = ""
                    parsed = parse_cars_com_listing_html(
                        content,
                        listing_url=listing_url,
                        rank=i,
                        vehicle_id=f"nova-act-{i}",
                    )
                    if parsed:
                        parsed_list.append(parsed)
                        logger.info(
                            "Nova Act browser: parsed listing %d title=%s price=%s images=%d",
                            i,
                            (parsed.get("title") or "")[:50],
                            parsed.get("price"),
                            len(parsed.get("image_urls") or []),
                        )
                    else:
                        logger.warning("Nova Act browser: parse failed for listing %d", i)
                    # Back to search results for next listing
                    nova.page.goto(search_url)
                except Exception as e:
                    logger.warning("Nova Act browser: listing %d failed: %s", i, e)
                    try:
                        nova.page.goto(search_url)
                    except Exception:
                        pass
    except Exception as e:
        logger.exception("Nova Act browser: run failed: %s", e)
        return parsed_list

    # Return whatever we got: 0 to num_listings (empty list if none)
    logger.info(
        "Nova Act browser: collected %d listings (requested up to %d); returning as-is.",
        len(parsed_list),
        num_listings,
    )
    return parsed_list


async def _run_workflow_and_get_results(
    workflow_name: str,
    model_id: str,
    region: str,
) -> List[VehicleListingResult]:
    """Create workflow run, poll until done, return parsed results (or [])."""
    import boto3

    _ensure_nova_act_api_key_env()
    ak, sk = _get_aws_credentials()
    if not ak or not sk:
        logger.debug("Nova Act workflow: no AWS credentials; skipping")
        return []

    kwargs = {"region_name": region, "aws_access_key_id": ak, "aws_secret_access_key": sk}
    client = boto3.client("nova-act", **kwargs)

    def _create():
        return client.create_workflow_run(
            workflowDefinitionName=workflow_name,
            modelId=model_id,
            clientInfo={"compatibilityVersion": 1, "sdkVersion": "1.0"},
        )

    try:
        run = await asyncio.to_thread(_create)
    except Exception as e:
        logger.warning("Nova Act create_workflow_run failed: %s", e)
        return []

    run_id = run.get("workflowRunId")
    if not run_id:
        return []

    status = run.get("status", "RUNNING")
    deadline = time.monotonic() + 120
    poll_interval = 5

    while status == "RUNNING":
        if time.monotonic() > deadline:
            logger.warning("Nova Act workflow run timed out: %s", run_id)
            return []
        await asyncio.sleep(poll_interval)

        def _get():
            return client.get_workflow_run(
                workflowDefinitionName=workflow_name,
                workflowRunId=run_id,
            )

        run = await asyncio.to_thread(_get)
        status = run.get("status", "")

    if status != "SUCCEEDED":
        logger.warning("Nova Act workflow run ended with status %s: %s", status, run_id)
        return []

    s = get_settings()
    if s.nova_act_result_s3_bucket and s.nova_act_result_s3_prefix:
        try:
            s3 = boto3.client("s3", **kwargs)
            prefix = f"{s.nova_act_result_s3_prefix.rstrip('/')}/{run_id}"
            list_resp = s3.list_objects_v2(
                Bucket=s.nova_act_result_s3_bucket,
                Prefix=prefix,
                MaxKeys=5,
            )
            for obj in list_resp.get("Contents") or []:
                key = obj.get("Key", "")
                if key.endswith(".json"):
                    body = s3.get_object(Bucket=s.nova_act_result_s3_bucket, Key=key)
                    data = json.loads(body["Body"].read().decode())
                    if isinstance(data, list):
                        return _parse_listings_to_results(data)
                    if isinstance(data, dict) and "listings" in data:
                        return _parse_listings_to_results(data["listings"])
        except Exception as e:
            logger.warning("Nova Act S3 result read failed: %s", e)

    return []


async def search_listings_nova_act(
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
    rows: int = 10,
) -> Tuple[List[VehicleListingResult], int, Optional[PriceStats]]:
    """
    Search for vehicles using Nova Act only: workflow (S3) or browser (cars.com via SDK).
    When API key is set, uses browser path (same as run_nova_act_cars.py). Results cached 30 min.
    """
    logger.info(
        "Nova Act search_listings_nova_act CALLED: make=%s model=%s zip_code=%s radius=%s year_min=%s year_max=%s car_type=%s price_min=%s price_max=%s max_mileage=%s rows=%s",
        make,
        model,
        zip_code,
        radius_miles,
        year_min,
        year_max,
        car_type,
        price_min,
        price_max,
        max_mileage,
        rows,
    )

    key = _cache_key(
        zip_code, make, model, year_min, year_max, price_min, price_max, max_mileage, car_type
    )
    async with _cache_lock:
        if key in _cache:
            ts, results, total, stats = _cache[key]
            if time.monotonic() - ts < _CACHE_TTL_SEC:
                logger.info("Nova Act: cache HIT for this search; returning %d cached results", len(results))
                return results, total, stats
            del _cache[key]
        while len(_cache) >= _CACHE_MAX_SIZE:
            oldest_key = min(_cache, key=lambda k: _cache[k][0])
            del _cache[oldest_key]

    s = get_settings()
    region = s.nova_act_region or "us-east-1"
    model_id = s.nova_act_model_id or "us.amazon.nova-2-lite-v1:0"
    workflow_name = (s.nova_act_workflow_name or "").strip()
    api_key = _get_nova_act_api_key()

    if not has_nova_act_configured():
        logger.warning(
            "Nova Act: not configured (no AWS creds and no Nova Act API key). Returning no results."
        )
        return [], 0, None

    if workflow_name and not api_key:
        # Have workflow config but no API key -> use workflow (S3 results)
        logger.info(
            "Nova Act PATH DECISION: using WORKFLOW (workflow_name=%s). Real data from deployed workflow.",
            workflow_name,
        )
        results = await _run_workflow_and_get_results(workflow_name, model_id, region)
    elif api_key:
        # API key set -> use Nova Act SDK browser (real cars.com data, same as run_nova_act_cars.py)
        logger.info(
            "Nova Act PATH DECISION: using BROWSER (Nova Act SDK). Real data from cars.com. make=%s model=%s zip=%s rows=%d",
            make,
            model,
            zip_code,
            min(rows, 10),
        )
        num_listings = min(rows, 10)
        logger.info("Nova Act browser: invoking _run_nova_act_browser_sync in thread (this will open cars.com)...")
        parsed_list = await asyncio.to_thread(
            _run_nova_act_browser_sync,
            make,
            model,
            year_min=year_min,
            year_max=year_max,
            zip_code=zip_code,
            radius_miles=radius_miles,
            car_type=car_type,
            price_min=price_min,
            price_max=price_max,
            max_mileage=max_mileage,
            num_listings=num_listings,
            api_key=api_key,
        )
        results = _parse_listings_to_results(parsed_list) if parsed_list else []
        if len(results) == 0:
            logger.info("Nova Act browser: no listings collected; returning empty list.")
        elif len(results) < num_listings:
            logger.info(
                "Nova Act browser: returning %d listings (requested up to %d); fewer results available.",
                len(results),
                num_listings,
            )
        else:
            logger.info(
                "Nova Act browser: DONE. Returned %d VehicleListingResults (real cars.com listings).",
                len(results),
            )
    else:
        # No workflow and no API key -> no Nova Act path; return empty (Bedrock synthetic path removed)
        logger.warning(
            "Nova Act: no workflow and no API key. Set AWS_NOVA_HACKATHON_API_KEY or NOVA_ACT_API_KEY for browser data, or use MarketCheck (CAR_SEARCH_PROVIDER=marketcheck). Returning no results."
        )
        results = []

    if rows and len(results) > rows:
        results = results[:rows]
    total = len(results)
    price_stats = _compute_price_stats(results)

    async with _cache_lock:
        _cache[key] = (time.monotonic(), results, total, price_stats)

    return results, total, price_stats
