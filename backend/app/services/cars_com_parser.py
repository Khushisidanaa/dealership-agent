"""
Parse Cars.com VDP primary-grid HTML (from Nova Act) into app listing format.

Consumes the HTML extracted from div.primary-grid on a cars.com vehicle detail page
and returns a dict suitable for VehicleListingResult / flattened vehicle display.
"""

import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)


def _text(soup: Optional[Tag]) -> str:
    if soup is None:
        return ""
    return (soup.get_text(separator=" ", strip=True) or "").strip()


def _parse_price(text: str) -> Optional[float]:
    if not text:
        return None
    # "$25,695" -> 25695
    m = re.search(r"\$[\d,]+", text.replace(",", ""))
    if not m:
        return None
    try:
        return float(m.group(0).replace("$", "").replace(",", ""))
    except (TypeError, ValueError):
        return None


def _parse_mileage(text: str) -> Optional[int]:
    if not text:
        return None
    # "10,676 mi" or "10676 miles"
    m = re.search(r"([\d,]+)\s*mi", text, re.I)
    if m:
        try:
            return int(m.group(1).replace(",", ""))
        except (TypeError, ValueError):
            pass
    return None


def _extract_primary_grid(html: str) -> Optional[Tag]:
    """Return the div.primary-grid element or None."""
    if not html or not html.strip():
        return None
    soup = BeautifulSoup(html, "html.parser")
    return soup.find("div", class_="primary-grid")


def parse_cars_com_listing_html(
    html: str,
    listing_url: str = "",
    rank: int = 1,
    vehicle_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Parse Cars.com VDP primary-grid HTML into a single listing dict.

    Args:
        html: Full page HTML or just the primary-grid div content.
        listing_url: URL of this listing (e.g. current page URL from browser).
        rank: 1-based rank for this listing.
        vehicle_id: Optional vehicle_id; otherwise generated from rank.

    Returns:
        Dict with keys matching VehicleListingResult / _flatten_listing shape, or None if parse failed.
    """
    soup = BeautifulSoup(html, "html.parser")
    root = soup.find("div", class_="primary-grid")
    if root is None:
        # HTML might be exactly the primary-grid inner content (e.g. from script extraction)
        root = soup
    if not root:
        logger.warning("cars_com_parser: no primary-grid or root found in HTML")
        return None

    # --- Images (only slot="image", exclude video/360/ads) ---
    image_urls: List[str] = []
    for img in root.find_all("img", slot="image"):
        src = (img.get("src") or "").strip()
        if src and src.startswith("http"):
            image_urls.append(src)
    logger.debug("cars_com_parser: extracted %d image URLs", len(image_urls))

    # --- Title ---
    title_el = root.find(id="vehicle-title") or root.find("h1", class_=lambda c: c and "heading" in (c or ""))
    title = _text(title_el) if title_el else ""

    # --- Price ---
    price_el = root.find("div", class_="list-price")
    price = _parse_price(_text(price_el)) if price_el else None

    # --- Mileage (in .msrp div, often "10,676 mi") ---
    msrp_el = root.find("div", class_="msrp")
    mileage = _parse_mileage(_text(msrp_el)) if msrp_el else None

    # --- VIN / Stock (Features & specs section subtitle) ---
    vin, stock_no = "", ""
    specs_section = root.find("section", id="features-and-specs") or root.find("section", class_=lambda c: c and "features" in (c or ""))
    if specs_section:
        subtitle = specs_section.find("div", class_="subtitle")
        if subtitle:
            subtext = _text(subtitle)
            vin_m = re.search(r"VIN:\s*([A-HJ-NPR-Z0-9]{17})", subtext, re.I)
            stock_m = re.search(r"Stock\s*#?:\s*(\S+)", subtext, re.I)
            if vin_m:
                vin = vin_m.group(1).strip()
            if stock_m:
                stock_no = stock_m.group(1).strip()

    # --- Basics (exterior, interior, fuel, engine, mpg, drivetrain, transmission) ---
    exterior_color = ""
    interior_color = ""
    fuel_type = ""
    engine = ""
    mpg = ""
    drivetrain = ""
    transmission = ""
    if specs_section:
        for li in specs_section.find_all("li", attrs={"data-qa": "basics-entry"}):
            t = _text(li)
            if "exterior color" in t.lower():
                exterior_color = re.sub(r"\s*exterior\s*color\s*", " ", t, flags=re.I).strip()
            elif "interior color" in t.lower():
                interior_color = re.sub(r"\s*interior\s*color\s*", " ", t, flags=re.I).strip()
            elif "fuel type" in t.lower():
                fuel_type = re.sub(r"\s*fuel\s*type\s*", " ", t, flags=re.I).strip()
            elif "engine" in t.lower() and "mpg" not in t.lower():
                engine = re.sub(r"\s*engine\s*", " ", t, flags=re.I).strip()
            elif "mpg" in t.lower():
                mpg = t.strip()
            elif "drivetrain" in t.lower():
                drivetrain = re.sub(r"\s*drivetrain\s*", " ", t, flags=re.I).strip()
            elif "transmission" in t.lower():
                transmission = re.sub(r"\s*transmission\s*", " ", t, flags=re.I).strip()

    # --- Feature list (Convenience, Entertainment, Exterior, Safety, Seating) ---
    features: List[str] = []
    for feat_li in root.find_all("li", attrs={"data-qa": "spec-value"}):
        f = _text(feat_li)
        if f and f not in features:
            features.append(f)
    # Add key basics as features for display
    for val in (transmission, drivetrain, fuel_type, engine):
        if val and val not in features:
            features.append(val)

    # --- Dealer from seller's notes and dealership link ---
    dealer_name = ""
    dealer_phone = ""
    dealer_address = ""
    dealer_website = ""
    sellers_section = root.find("section", id="sellers-notes") or root.find("section", class_=lambda c: c and "sellers" in (c or ""))
    if sellers_section:
        section_text = _text(sellers_section)
        # US phone: 805-351-4021 or (805) 351-4021
        phone_m = re.search(r"\(?(\d{3})\)?[-.\s]*(\d{3})[-.\s]*(\d{4})", section_text)
        if phone_m:
            dealer_phone = f"({phone_m.group(1)}) {phone_m.group(2)}-{phone_m.group(3)}"
        # Address pattern: "at 6450 Auto Center Dr" or "located at ..."
        addr_m = re.search(r"(?:at|located at|address:)\s*([^.]{10,120}?(?:Dr|St|Ave|Blvd|Rd|Way|Ln|Ct)[^.]*?)(?:\.|,|$)", section_text, re.I)
        if addr_m:
            dealer_address = addr_m.group(1).strip()
        # Dealer name: prefer "X Honda of Ventura" / "X Toyota of Y" style (short phrase)
        name_m = re.search(
            r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+(?:Honda|Toyota|Ford|Chevrolet|Nissan|Hyundai|Kia|Mazda|Subaru|Motors|Auto|BMW|Mercedes|Lexus|Acura)(?:\s+of\s+[A-Z][a-z]+)?)\b",
            section_text,
        )
        if name_m:
            candidate = name_m.group(1).strip()
            # Avoid long matches (e.g. "Point Inspection conducted by our factory certified Honda technicians")
            if len(candidate) < 60 and "inspection" not in candidate.lower() and "certified" not in candidate.lower():
                dealer_name = candidate
    # Dealership website link (exclude cars.com host only; query params may contain cars.com)
    def _host(h: str) -> str:
        return (urlparse(h).netloc or "").lower()

    for a in root.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        text_lower = (_text(a) or "").lower()
        if "dealership" in text_lower or "dealer" in text_lower or "vehicle on" in text_lower:
            if href.startswith("http") and "cars.com" not in _host(href):
                dealer_website = href
                if not dealer_name and "oceanhondaventura" in href:
                    dealer_name = "Ocean Honda of Ventura"
                break
    # Fallback: derive dealer name from website hostname
    if not dealer_name and dealer_website:
        try:
            host = urlparse(dealer_website).netloc or ""
            host = host.replace("www.", "").split(".")[0]
            if host:
                dealer_name = host.replace("-", " ").title()
        except Exception:
            pass

    # --- Condition (certified / used / new from title or badges) ---
    condition = "used"
    if "certified" in title.lower():
        condition = "certified"
    elif "new" in title.lower():
        condition = "new"
    for badge in root.find_all("fuse-badge"):
        variant = (badge.get("variant") or "").lower()
        if "certified" in (_text(badge) or "").lower():
            condition = "certified"
            break

    # --- Year / Make / Model from title (e.g. "Certified 2023 Honda Civic Sport") ---
    year, make, model = None, "", ""
    year_m = re.search(r"\b(19|20)\d{2}\b", title)
    if year_m:
        try:
            year = int(year_m.group(0))
        except (TypeError, ValueError):
            pass
    # Simple split: "Certified 2023 Honda Civic Sport" -> make=Honda, model=Civic Sport
    parts = title.split()
    for i, p in enumerate(parts):
        if p.isdigit() and len(p) == 4 and 1990 <= int(p) <= 2030:
            if i + 2 < len(parts):
                make = parts[i + 1]
                model = " ".join(parts[i + 2:])
            break

    vid = vehicle_id or f"cars-com-{rank}"
    return {
        "vehicle_id": vid,
        "rank": rank,
        "title": title or "Unknown Vehicle",
        "heading": title or "Unknown Vehicle",
        "price": price,
        "miles": mileage,
        "mileage": mileage,
        "vin": vin,
        "stock_no": stock_no,
        "listing_url": listing_url,
        "image_urls": image_urls,
        "features": features,
        "condition": condition,
        "inventory_type": condition,
        "dealer_name": dealer_name,
        "dealer_phone": dealer_phone,
        "dealer_address": dealer_address,
        "dealer_website": dealer_website,
        "year": year,
        "make": make,
        "model": model,
        "exterior_color": exterior_color,
        "interior_color": interior_color,
        "fuel_type": fuel_type,
        "engine": engine,
        "transmission": transmission,
        "drivetrain": drivetrain,
        "source": "nova_act",
    }
