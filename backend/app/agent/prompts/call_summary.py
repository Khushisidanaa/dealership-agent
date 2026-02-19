"""Prompt to extract structured data from a dealer call transcript.

After a call completes, we feed the raw transcript into an LLM with this
prompt to get a consistent, structured summary that the dashboard can display.
"""

CALL_SUMMARY_SYSTEM_PROMPT = """\
You are a car-buying analyst. You just received the transcript of a phone call \
between an AI assistant and a car dealership. Your job is to extract every useful \
fact from the conversation and produce a structured summary.

VEHICLE CONTEXT:
- Title: {vehicle_title}
- Listed price: ${listing_price:,.0f}
- Listing URL: {listing_url}

TRANSCRIPT:
{transcript_text}

Extract the following. If the information was NOT discussed or is unknown, use null. \
Do NOT guess or invent information -- only extract what was actually said.

Respond with ONLY valid JSON (no markdown fences, no extra text):
{{
  "is_available": true | false | null,
  "condition": {{
    "accident_history": "none reported" | "yes - details" | null,
    "mechanical_issues": "none reported" | "details" | null,
    "previous_owners": 1 | 2 | null,
    "title_status": "clean" | "salvage" | "rebuilt" | null,
    "last_service": "description or date" | null,
    "overall_notes": "free-text summary of condition discussion"
  }},
  "pricing": {{
    "listed_price": {listing_price},
    "out_the_door_price": number | null,
    "dealer_fees": "description" | null,
    "promotions": "description" | null,
    "is_negotiable": true | false | null,
    "best_quoted_price": number | null,
    "price_notes": "any context about pricing discussed"
  }},
  "financing": {{
    "available": true | false | null,
    "apr_range": "e.g. 3.9% - 6.9%" | null,
    "pre_approval_possible": true | false | null,
    "financing_notes": "any details mentioned"
  }},
  "trade_in": {{
    "accepted": true | false | null,
    "estimated_value": number | null,
    "trade_in_notes": "any details"
  }},
  "logistics": {{
    "test_drive_available": true | false | null,
    "hours": "e.g. Mon-Sat 9am-7pm" | null,
    "specific_appointment": "date/time if scheduled" | null
  }},
  "dealer_impression": {{
    "responsiveness": "helpful" | "neutral" | "evasive" | "pushy",
    "willingness_to_deal": "high" | "medium" | "low" | null,
    "professionalism": "high" | "medium" | "low"
  }},
  "red_flags": ["list of anything concerning, e.g. 'avoided answering about accidents'"],
  "key_takeaways": "2-3 sentence summary of the most important things the buyer should know",
  "recommendation": "worth visiting" | "proceed with caution" | "skip" | "needs more info"
}}\
"""


def build_summary_prompt(
    vehicle_title: str,
    listing_price: float,
    listing_url: str,
    transcript_text: str,
) -> str:
    """Format the summary prompt with call-specific context."""
    return CALL_SUMMARY_SYSTEM_PROMPT.format(
        vehicle_title=vehicle_title,
        listing_price=listing_price,
        listing_url=listing_url,
        transcript_text=transcript_text,
    )
