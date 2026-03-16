"""
Dashboard PDF export using Amazon Bedrock (DeepSeek) and reportlab.

Replaces Foxit Document Generation: generates the report content with Bedrock
(known issues and dealer visit tips per make/model) and renders PDF locally with reportlab.
"""

import io
import logging
import re
from datetime import datetime
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
)

from app.config import get_settings
from app.services.bedrock_chat_service import invoke_converse_sync, has_bedrock_configured

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data preparation (same contract as legacy Foxit flow)
# ---------------------------------------------------------------------------

def _format_availability(details: dict | None) -> str:
    if not details:
        return "Unknown"
    av = details.get("is_available")
    if av is True:
        return "Available"
    if av is False:
        return "Sold / Unavailable"
    return "Unknown"


def _format_verdict(details: dict | None) -> str:
    if not details:
        return ""
    return details.get("recommendation") or ""


def _format_notes(
    details: dict | None,
    summary: str | None,
    test_drive: str | None,
) -> str:
    parts = []
    if details and details.get("key_takeaways"):
        parts.append(str(details["key_takeaways"]))
    if summary and summary not in parts:
        parts.append(summary)
    if test_drive:
        parts.append(f"Test drive: {test_drive}")
    return " | ".join(parts) if parts else "-"


def _parse_make_model_year(v: dict) -> tuple[str, str, str]:
    """Infer make, model, year from vehicle dict (build info or title/heading)."""
    build = v.get("build") or {}
    if isinstance(build, dict):
        make = (build.get("make") or "").strip()
        model = (build.get("model") or "").strip()
        year = build.get("year")
        if make and model and year is not None:
            return make, model, str(year)
    title = (v.get("title") or v.get("heading") or "").strip()
    if not title:
        return "", "", ""
    # e.g. "2023 Honda Civic Sport" or "Certified 2023 Honda Civic Sport"
    year_s = ""
    make_s = ""
    model_s = ""
    tokens = title.split()
    for i, t in enumerate(tokens):
        if re.match(r"^19\d{2}|20\d{2}$", t):
            year_s = t
            rest = tokens[i + 1:]
            if len(rest) >= 2:
                make_s = rest[0]
                model_s = " ".join(rest[1:])
            break
    return make_s, model_s, year_s


def prepare_dashboard_data(
    vehicles: list[dict],
    communication_status: list[dict],
    bookings_by_vehicle: dict[str, dict],
) -> dict[str, Any]:
    """Transform dashboard data for PDF report. Same contract as legacy Foxit flow."""
    comm_by_id = {c["vehicle_id"]: c for c in communication_status}
    contacted_ids = {
        vid
        for vid, c in comm_by_id.items()
        if c.get("call_made") or c.get("text_sent")
    }

    call_results = []
    all_vehicles = []
    # All vehicles list with make/model/year for Bedrock (call_results + all_vehicles combined)
    all_vehicle_rows: list[dict] = []

    for v in vehicles:
        vid = v.get("vehicle_id", "")
        comm = comm_by_id.get(vid) or {}
        details = comm.get("call_details") or {}
        summary = comm.get("response") or ""
        booking = bookings_by_vehicle.get(vid)
        test_drive = ""
        if booking:
            test_drive = f"{booking.get('scheduled_date', '')} at {booking.get('scheduled_time', '')}".strip()

        title = v.get("title") or v.get("heading") or "Unknown"
        price_val = v.get("price")
        price_str = f"${price_val:,.0f}" if price_val is not None else "N/A"
        miles_val = v.get("mileage") or v.get("miles")
        miles_str = f"{miles_val:,} mi" if miles_val is not None else "N/A"
        dealer = v.get("dealer_name") or ""
        make, model, year = _parse_make_model_year(v)

        row = {
            "heading": title,
            "price": price_str,
            "miles": miles_str,
            "dealer_name": dealer,
            "make": make,
            "model": model,
            "year": year,
        }

        if vid in contacted_ids:
            call_results.append({
                **row,
                "availability": _format_availability(details),
                "verdict": _format_verdict(details),
                "notes": _format_notes(details, summary, test_drive or None),
            })
        else:
            all_vehicles.append({k: v for k, v in row.items() if k in ("heading", "price", "miles", "dealer_name")})

        all_vehicle_rows.append(row)

    # Summary for report header
    total = len(call_results) + len(all_vehicles)
    if total == 0:
        report_summary = "No vehicles in this report."
    elif len(call_results) == 0:
        report_summary = f"{len(all_vehicles)} vehicle{'s' if len(all_vehicles) != 1 else ''} in your shortlist."
    elif len(all_vehicles) == 0:
        report_summary = f"{len(call_results)} vehicle{'s' if len(call_results) != 1 else ''} contacted. See call details below."
    else:
        report_summary = f"{total} vehicles total — {len(call_results)} contacted with call results, {len(all_vehicles)} in your shortlist."

    if not call_results and all_vehicles:
        call_results = [{
            "heading": "(No dealer calls yet)",
            "price": "-",
            "dealer_name": "-",
            "availability": "-",
            "verdict": "-",
            "notes": "Run the analyze flow to call dealers and populate this section.",
        }]
    elif not call_results:
        call_results = [{
            "heading": "(No data)",
            "price": "-",
            "dealer_name": "-",
            "availability": "-",
            "verdict": "-",
            "notes": "Add vehicles and run analyze to see call results.",
        }]

    return {
        "report_summary": report_summary,
        "call_results": call_results,
        "all_vehicles": all_vehicles,
        "all_vehicle_rows": all_vehicle_rows,
    }


# ---------------------------------------------------------------------------
# Bedrock: known issues and dealer visit tips per make/model
# ---------------------------------------------------------------------------

KNOWN_ISSUES_SYSTEM = """You are an automotive expert. You provide concise, factual guidance for used car buyers.
Output only the requested sections in plain text. Use short bullet points. No preamble or disclaimer."""

KNOWN_ISSUES_USER_TEMPLATE = """For this vehicle: {description}

Provide two sections:

1) WELL-KNOWN PROBLEMS
- List 3–6 well-known issues, recalls, or common failures for this make, model, and year (if year given). Be specific (e.g. transmission, battery, rust, electronics).
- If it's an EV or hybrid (Tesla, Bolt, Leaf, etc.), always include battery degradation and how to verify battery health at the dealer.

2) WHAT TO CHECK AT THE DEALER (in-person visit)
- List 4–8 specific things the buyer should inspect or ask about when visiting the dealer: mechanical, paperwork, test drive, and for EVs/hybrids always include checking battery state of health or range.
- Be practical and actionable."""


def fetch_known_issues_and_visit_tips(make: str, model: str, year: str, title: str) -> str:
    """Call Bedrock (DeepSeek) to get known problems and dealer visit tips for this make/model/year."""
    if not has_bedrock_configured():
        return ""
    description = title or f"{year} {make} {model}".strip()
    if not description.strip():
        return ""
    user_msg = KNOWN_ISSUES_USER_TEMPLATE.format(description=description)
    try:
        text = invoke_converse_sync(
            [{"role": "user", "content": user_msg}],
            system=KNOWN_ISSUES_SYSTEM,
            max_tokens=1024,
            temperature=0.3,
        )
        return (text or "").strip()
    except Exception as e:
        log.warning("Bedrock known-issues call failed for %s: %s", description, e)
        return ""


def fetch_insights_for_vehicles(all_vehicle_rows: list[dict]) -> dict[str, str]:
    """
    Fetch Bedrock insights (known issues + visit tips) per vehicle.
    Deduplicates by (make, model, year) to avoid duplicate API calls.
    Returns dict keyed by vehicle heading -> insight text.
    """
    seen: set[tuple[str, str, str]] = set()
    key_to_text: dict[tuple[str, str, str], str] = {}
    for row in all_vehicle_rows:
        make = (row.get("make") or "").strip()
        model = (row.get("model") or "").strip()
        year = (row.get("year") or "").strip()
        title = (row.get("heading") or "").strip()
        key = (make, model, year)
        if key in seen:
            continue
        seen.add(key)
        text = fetch_known_issues_and_visit_tips(make, model, year, title)
        if text:
            key_to_text[key] = text
    # Map each vehicle row to the text for its make/model/year
    result: dict[str, str] = {}
    for row in all_vehicle_rows:
        make = (row.get("make") or "").strip()
        model = (row.get("model") or "").strip()
        year = (row.get("year") or "").strip()
        heading = (row.get("heading") or "").strip()
        key = (make, model, year)
        result[heading] = key_to_text.get(key, "")
    return result


# ---------------------------------------------------------------------------
# PDF build with reportlab
# ---------------------------------------------------------------------------

def _col_widths(n: int) -> list[float]:
    if n == 6:
        return [2.2 * inch, 0.8 * inch, 1.2 * inch, 1.0 * inch, 1.0 * inch, 1.8 * inch]
    if n == 4:
        return [2.5 * inch, 0.9 * inch, 0.9 * inch, 1.5 * inch]
    return [3.0 * inch] * n


def _add_table(doc_flow: list, data: list[dict], headers: list[str], col_keys: list[str]) -> None:
    if not data:
        return
    rows = [headers]
    for r in data:
        rows.append([str(r.get(k, "")) for k in col_keys])
    n = len(headers)
    t = Table(rows, colWidths=_col_widths(n))
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4472C4")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
        ("TOPPADDING", (0, 0), (-1, 0), 8),
        ("BACKGROUND", (0, 1), (-1, -1), colors.white),
        ("TEXTCOLOR", (0, 1), (-1, -1), colors.black),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    doc_flow.append(t)


def generate_dashboard_pdf(data: dict[str, Any]) -> bytes:
    """
    Build PDF from dashboard data using reportlab. Uses Bedrock for known issues
    and dealer visit tips when configured.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        rightMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Heading1"],
        fontSize=16,
        spaceAfter=6,
    )
    heading_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontSize=12,
        spaceBefore=12,
        spaceAfter=6,
    )
    body_style = styles["Normal"]

    flow: list = []

    # Title and date
    flow.append(Paragraph("Vehicle Research Report", title_style))
    flow.append(Paragraph(f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M')}", body_style))
    flow.append(Spacer(1, 0.15 * inch))
    flow.append(Paragraph(data.get("report_summary", ""), body_style))
    flow.append(Spacer(1, 0.2 * inch))

    # Dealer Call Results
    flow.append(Paragraph("Dealer Call Results", heading_style))
    flow.append(Paragraph("Vehicles we contacted — availability, verdict, and notes from dealer calls.", body_style))
    flow.append(Spacer(1, 0.1 * inch))
    call_results = data.get("call_results") or []
    _add_table(
        flow,
        call_results,
        ["Vehicle", "Price", "Dealer", "Availability", "Verdict", "Notes"],
        ["heading", "price", "dealer_name", "availability", "verdict", "notes"],
    )
    flow.append(Spacer(1, 0.25 * inch))

    # All Vehicles
    flow.append(Paragraph("All Vehicles", heading_style))
    flow.append(Paragraph("Your shortlisted vehicles.", body_style))
    flow.append(Spacer(1, 0.1 * inch))
    all_vehicles = data.get("all_vehicles") or []
    _add_table(
        flow,
        all_vehicles,
        ["Vehicle", "Price", "Mileage", "Dealer"],
        ["heading", "price", "miles", "dealer_name"],
    )
    flow.append(Spacer(1, 0.3 * inch))

    # Known issues and what to check at the dealer (Bedrock)
    all_vehicle_rows = data.get("all_vehicle_rows") or []
    insights = fetch_insights_for_vehicles(all_vehicle_rows) if all_vehicle_rows else {}
    if insights:
        flow.append(Paragraph("Known Issues & What to Check at the Dealer", heading_style))
        flow.append(Paragraph(
            "For each make and model below, use this list when you visit the dealer to inspect the vehicle.",
            body_style,
        ))
        flow.append(Spacer(1, 0.15 * inch))
        for row in all_vehicle_rows:
            heading = (row.get("heading") or "").strip()
            text = insights.get(heading, "").strip()
            if not text:
                continue
            flow.append(Paragraph(f"<b>{heading}</b>", body_style))
            # Split into lines and add as paragraphs so newlines are preserved
            for block in text.split("\n\n"):
                block = block.strip()
                if block:
                    # Escape HTML so model output cannot inject tags
                    safe = block.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                    flow.append(Paragraph(safe.replace("\n", "<br/>"), body_style))
            flow.append(Spacer(1, 0.15 * inch))

    doc.build(flow)
    buf.seek(0)
    return buf.read()
