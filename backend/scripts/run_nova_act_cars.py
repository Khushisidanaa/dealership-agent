#!/usr/bin/env python3
"""
Run Nova Act SDK against cars.com: build URL from input, open results page,
retrieve first 5 listings by clicking each and getting page source, then log the data.

Usage:
  cd backend && python scripts/run_nova_act_cars.py
  cd backend && python scripts/run_nova_act_cars.py --input ../docs/nova-act-input.json

What you need to provide:
  1. Nova Act API key — In backend/.env set AWS_NOVA_HACKATHON_API_KEY=your_key
     (from https://nova.amazon.com/act). The script uses it as NOVA_ACT_API_KEY for the SDK.
  2. Optional: --input path to a JSON file with keys: make, model, year_min, year_max,
     zip_code, radius_miles, car_type, price_min, price_max, max_mileage.
     Default: docs/nova-act-input.json in project root.
  3. Python 3.10+ and pip install nova-act (and playwright browsers: playwright install chrome).
"""

import json
import logging
import os
import sys
from pathlib import Path

# Add backend to path so we can import app.services
_backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_backend_dir))

# Load backend .env (AWS_NOVA_HACKATHON_API_KEY or NOVA_ACT_API_KEY)
try:
    from dotenv import load_dotenv
    load_dotenv(_backend_dir / ".env")
except ImportError:
    pass

def _get_nova_act_api_key() -> str:
    """API key from .env: AWS_NOVA_HACKATHON_API_KEY or NOVA_ACT_API_KEY (per Nova Act docs)."""
    key = (os.environ.get("AWS_NOVA_HACKATHON_API_KEY") or os.environ.get("NOVA_ACT_API_KEY") or "").strip()
    return key

from app.services.cars_com_url import build_cars_com_url_from_input
from app.services.cars_com_parser import parse_cars_com_listing_html

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def _extract_primary_grid(html: str) -> str:
    """Extract everything under <div class=\"primary-grid\"> from the page HTML."""
    if not html or not html.strip():
        return "(empty)"
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        div = soup.find("div", class_="primary-grid")
        if div is None:
            return "(no div.primary-grid found on page)"
        return str(div)
    except Exception as e:
        return f"(extract failed: {e})"


logger = logging.getLogger(__name__)

# Limit logged page source length so we don't flood console
MAX_PAGE_SOURCE_LOG = 2000

# ANSI: blue for HTML output, reset
BLUE = "\033[34m"
RESET = "\033[0m"
NUM_LISTINGS = 5

OUTPUT_DIR = _backend_dir / "test-collected-data"


def load_input(input_path: str | None) -> dict:
    """Load search input from JSON file or return default."""
    if input_path and os.path.isfile(input_path):
        with open(input_path, encoding="utf-8") as f:
            return json.load(f)
    # Default from docs/nova-act-input.json relative to project root
    project_root = Path(__file__).resolve().parent.parent.parent
    default = project_root / "docs" / "nova-act-input.json"
    if default.is_file():
        with open(default, encoding="utf-8") as f:
            return json.load(f)
    return {
        "make": "Honda",
        "model": "Civic",
        "year_min": 2020,
        "year_max": 2024,
        "zip_code": "90210",
        "radius_miles": 50,
        "car_type": "used",
        "price_min": 15000,
        "price_max": 35000,
        "max_mileage": 60000,
        "rows": 10,
    }


def run_nova_act_cars(input_data: dict, output_json: bool = False) -> list:
    """Build cars.com URL from search terms, run Nova Act, click first N listings, save HTML and parse to app format."""
    # Log search terms and build URL (same params the backend uses for Nova Act browser path)
    logger.info(
        "Nova Act script: search terms -> make=%s model=%s year_min=%s year_max=%s zip_code=%s radius_miles=%s car_type=%s price_min=%s price_max=%s max_mileage=%s rows=%s",
        input_data.get("make"),
        input_data.get("model"),
        input_data.get("year_min"),
        input_data.get("year_max"),
        input_data.get("zip_code"),
        input_data.get("radius_miles"),
        input_data.get("car_type"),
        input_data.get("price_min"),
        input_data.get("price_max"),
        input_data.get("max_mileage"),
        input_data.get("rows"),
    )
    url = build_cars_com_url_from_input(input_data)
    logger.info("Nova Act script: built cars.com URL with above search terms -> %s", url)

    try:
        from nova_act import NovaAct
    except ImportError:
        logger.error(
            "Nova Act SDK not installed. Run: pip install nova-act"
        )
        raise

    api_key = _get_nova_act_api_key()
    if not api_key:
        logger.error("Set AWS_NOVA_HACKATHON_API_KEY or NOVA_ACT_API_KEY in backend/.env (get key from https://nova.amazon.com/act)")
        raise SystemExit(1)

    num_listings = min(int(input_data.get("rows") or NUM_LISTINGS), 10)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    logger.info("Saving extracted HTML to %s (listings=%d)", OUTPUT_DIR, num_listings)

    parsed_list = []

    def _ordinal(n: int) -> str:
        return "1st" if n == 1 else "2nd" if n == 2 else "3rd" if n == 3 else f"{n}th"

    # ignore_https_errors=True avoids InvalidCertificate when cars.com loads third-party
    # ad/tracking pixels (e.g. rubiconproject.com) that can fail SSL verification
    with NovaAct(
        starting_page=url,
        nova_act_api_key=api_key,
        ignore_https_errors=True,
    ) as nova:
        for i in range(1, num_listings + 1):
            logger.info("--- Listing %d/%d ---", i, num_listings)
            try:
                nova.act(
                    f"Find and click on the {_ordinal(i)} vehicle listing link in the search results. "
                    f"If the {_ordinal(i)} listing is not visible on the screen, scroll down the results page until you can see it, then click it. "
                    "Click only the link that opens that specific vehicle's detail page. "
                    "Wait for the listing detail page to load."
                )
                listing_url = getattr(nova.page, "url", None) or ""
                content = (nova.page.content() or "") if callable(getattr(nova.page, "content", None)) else ""
                primary_grid_html = _extract_primary_grid(content) if isinstance(content, str) else "(empty)"
                # Save raw HTML
                out_path = OUTPUT_DIR / f"listing_{i}.txt"
                if not primary_grid_html.startswith("("):
                    out_path.write_text(primary_grid_html, encoding="utf-8")
                    logger.info("Saved %s", out_path)
                # Parse to app listing format
                parsed = parse_cars_com_listing_html(
                    primary_grid_html,
                    listing_url=listing_url,
                    rank=i,
                    vehicle_id=f"nova-act-{i}",
                )
                if parsed:
                    parsed_list.append(parsed)
                    logger.info(
                        "Parsed listing %d: title=%s price=%s mileage=%s images=%d",
                        i,
                        (parsed.get("title") or "")[:50],
                        parsed.get("price"),
                        parsed.get("miles"),
                        len(parsed.get("image_urls") or []),
                    )
                snippet = primary_grid_html[:MAX_PAGE_SOURCE_LOG] if primary_grid_html else "(empty)"
                if len(primary_grid_html) > MAX_PAGE_SOURCE_LOG:
                    snippet += "\n... (truncated)"
                print(BLUE + f"div.primary-grid (listing {i}):\n" + snippet + RESET)
                nova.page.goto(url)
            except Exception as e:
                logger.warning("Listing %d failed: %s", i, e)
                try:
                    nova.page.goto(url)
                except Exception:
                    pass

    # Return whatever we got: empty list if none, or 1 to num_listings
    if len(parsed_list) == 0:
        logger.info("Done. No listings collected; returning empty list.")
    else:
        logger.info("Done. Parsed %d listings (app format); returning as-is.", len(parsed_list))

    if output_json and parsed_list:
        json_path = OUTPUT_DIR / "listings_app_format.json"
        # Write shape that matches our API (list of vehicle dicts with keys used by frontend)
        out_vehicles = []
        for p in parsed_list:
            out_vehicles.append({
                "vehicle_id": p.get("vehicle_id"),
                "rank": p.get("rank"),
                "title": p.get("title"),
                "price": p.get("price"),
                "mileage": p.get("miles"),
                "condition": p.get("condition", "used"),
                "dealer_name": p.get("dealer_name"),
                "dealer_phone": p.get("dealer_phone"),
                "dealer_address": p.get("dealer_address"),
                "listing_url": p.get("listing_url"),
                "image_urls": p.get("image_urls") or [],
                "features": p.get("features") or [],
                "vin": p.get("vin"),
                "year": p.get("year"),
                "make": p.get("make"),
                "model": p.get("model"),
                "source": "nova_act",
            })
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump({"results": out_vehicles}, f, indent=2)
        logger.info("Wrote app-format JSON: %s", json_path)

    return parsed_list


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Run Nova Act on cars.com and log first N listing pages")
    parser.add_argument("--input", "-i", help="Path to JSON input (default: docs/nova-act-input.json)")
    parser.add_argument("--output-json", "-o", action="store_true", help="Write parsed listings to test-collected-data/listings_app_format.json")
    args = parser.parse_args()
    input_data = load_input(args.input)
    logger.info("Input: %s", json.dumps(input_data, indent=2))
    run_nova_act_cars(input_data, output_json=args.output_json)


if __name__ == "__main__":
    main()
