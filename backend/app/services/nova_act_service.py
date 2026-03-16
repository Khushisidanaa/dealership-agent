"""
Nova Act / Bedrock car search service.

Uses AWS Nova Act (workflow run) when a workflow is deployed, or Bedrock Converse
(DeepSeek) to generate listings. Supports Nova Act API key (AWS_NOVA_HACKATHON_API_KEY)
from nova.amazon.com/dev for hackathon/development; key is exposed as NOVA_ACT_API_KEY
for SDK/tooling. Includes in-memory cache (30 min TTL) to stay within rate limits.

Requests per search (uncached):
- Bedrock path (no workflow): 1 Converse API call.
- Workflow path: 1 create_workflow_run + N get_workflow_run (poll ~5s until done, max ~24) + 1 S3 list + 0–1 S3 get.
Cache hits: 0 external requests.
"""

import asyncio
import json
import logging
import os
import re
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
    """Nova Act API key (hackathon); never log this value."""
    return (get_settings().aws_nova_hackathon_api_key or "").strip()


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


def _bedrock_listings_from_prompt(
    zip_code: str,
    make: str,
    model: str,
    year_min: Optional[int],
    year_max: Optional[int],
    price_max: Optional[int],
    condition: str,
) -> List[VehicleListingResult]:
    """Synchronous: call Bedrock Converse (DeepSeek) to generate car listings JSON."""
    import boto3

    _ensure_nova_act_api_key_env()
    ak, sk = _get_aws_credentials()
    if not ak or not sk:
        # Allow boto3 default credential chain (env AWS_*, IAM role, etc.)
        logger.debug("Nova Act/Bedrock: using default AWS credential chain")

    s = get_settings()
    region = s.nova_act_region or "us-east-1"

    kwargs = {"region_name": region}
    if ak and sk:
        kwargs["aws_access_key_id"] = ak
        kwargs["aws_secret_access_key"] = sk

    year_part = ""
    if year_min or year_max:
        year_part = f" years {year_min or 'any'}-{year_max or 'any'}"
    price_part = f" under ${price_max}" if price_max else ""
    condition_part = (condition or "used").lower()

    prompt = f"""You are a car search assistant. Return a JSON array of exactly 10 vehicle listings that match these criteria:
- Location: zip code {zip_code}
- Make: {make or 'any'}
- Model: {model or 'any'}
- Year range: {year_part or 'any'}
- Condition: {condition_part}
- Price: {price_part or 'any'}

For each listing return a JSON object with these keys only (use empty string or 0 if unknown):
- title (e.g. "2022 Toyota Camry LE")
- price (number)
- mileage (number, odometer miles)
- listing_url (string, URL to the listing page)
- image_url (string, URL to the main vehicle photo; use a realistic CDN-style URL or empty if unknown)
- dealer_name (string)
- dealer_phone (string)
- dealer_address (string)
- year (number)
- make (string)
- model (string)

Return only the JSON array, no markdown or explanation. Example: [{{"title":"2022 Toyota Camry","price":28000,"mileage":15000,"listing_url":"...","image_url":"...",...}}, ...]"""

    try:
        # Use same DeepSeek model as chat so one Bedrock model works for both
        model_id = s.bedrock_chat_model_id or s.nova_act_model_id or "deepseek.v3.2"
        client = boto3.client("bedrock-runtime", **kwargs)

        response = client.converse(
            modelId=model_id,
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={
                "maxTokens": 4096,
                "temperature": 0.3,
            },
        )
        # Converse returns response["output"]["message"]["content"] = list of blocks with "text"
        output = response.get("output", {})
        message = output.get("message", {})
        content_list = message.get("content", []) or []
        text = ""
        for block in content_list:
            if isinstance(block, dict) and block.get("text"):
                text += block["text"]
        if not text.strip():
            return []
        # Strip markdown code block if present
        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```\w*\n?", "", text)
            text = re.sub(r"\n?```\s*$", "", text)
        data = json.loads(text)
        if not isinstance(data, list):
            return []
        return _parse_listings_to_results(data)
    except Exception as e:
        logger.exception("Bedrock Converse failed: %s", e)
        return []


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
            media = MediaInfo(photo_links=image_urls, photo_links_cached=[])

            dealer = DealerInfo(
                name=dealer_name,
                phone=dealer_phone,
                full_address=dealer_address,
            )
            build = BuildInfo(year=year, make=make, model=model)
            results.append(
                VehicleListingResult(
                    vehicle_id=str(row.get("vehicle_id") or f"nova-{i + 1}"),
                    rank=i + 1,
                    heading=title,
                    title=title,
                    price=price,
                    miles=miles,
                    dealer=dealer,
                    build=build,
                    media=media,
                    image_urls=image_urls,
                    listing_url=listing_url,
                    source="nova_act",
                    inventory_type="used",
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
    Search for vehicles using Nova Act (workflow if deployed) or Bedrock Nova Lite.
    Results are cached 30 min by (zip, make, model, filters) to reduce API usage (stay under 5000 RPD).
    """
    key = _cache_key(
        zip_code, make, model, year_min, year_max, price_min, price_max, max_mileage, car_type
    )
    async with _cache_lock:
        if key in _cache:
            ts, results, total, stats = _cache[key]
            if time.monotonic() - ts < _CACHE_TTL_SEC:
                return results, total, stats
            del _cache[key]
        while len(_cache) >= _CACHE_MAX_SIZE:
            oldest_key = min(_cache, key=lambda k: _cache[k][0])
            del _cache[oldest_key]

    s = get_settings()
    region = s.nova_act_region or "us-east-1"
    model_id = s.nova_act_model_id or "us.amazon.nova-2-lite-v1:0"
    workflow_name = (s.nova_act_workflow_name or "").strip()

    if not has_nova_act_configured():
        logger.debug("Nova Act/Bedrock car search not configured (missing AWS credentials); returning no results")
        return [], 0, None

    if workflow_name:
        results = await _run_workflow_and_get_results(workflow_name, model_id, region)
    else:
        results = await asyncio.to_thread(
            _bedrock_listings_from_prompt,
            zip_code,
            make,
            model,
            year_min,
            year_max,
            price_max,
            car_type,
        )

    if rows and len(results) > rows:
        results = results[:rows]
    total = len(results)
    price_stats = _compute_price_stats(results)

    async with _cache_lock:
        _cache[key] = (time.monotonic(), results, total, price_stats)

    return results, total, price_stats
