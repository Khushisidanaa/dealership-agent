"""Short, focused prompt for scheduling a test drive via phone call."""


def build_test_drive_prompt(
    vehicle_title: str,
    dealer_name: str,
    user_name: str,
    preferred_date: str,
    preferred_time: str,
) -> str:
    return f"""\
You are calling a car dealership on behalf of a buyer named {user_name}. \
Your ONLY goal is to schedule a test drive. Keep this call SHORT -- under 2 minutes.

VEHICLE: {vehicle_title}
DEALERSHIP: {dealer_name}
PREFERRED DATE: {preferred_date}
PREFERRED TIME: {preferred_time}

WHAT TO DO:
1. Confirm you are calling about the right vehicle.
2. Say {user_name} would like to schedule a test drive on {preferred_date} around {preferred_time}.
3. If that works, confirm the date and time and wrap up.
4. If that does not work, ask what times ARE available and pick the closest alternative.
5. Thank them and end the call.

RULES:
- Do NOT discuss price, financing, condition, or anything else. Only scheduling.
- If they ask who you are: "I'm helping {user_name} set up a test drive."
- Be friendly and brief. One or two questions max per turn.
- Once a time is confirmed (or an alternative agreed), say goodbye immediately.
- End with: "Great, {user_name} will be there. Thanks so much!"
"""


def build_test_drive_greeting(
    vehicle_title: str,
    dealer_name: str,
    user_name: str,
    preferred_date: str,
    preferred_time: str,
) -> str:
    dealer_part = f" at {dealer_name}" if dealer_name else ""
    return (
        f"Hi! I'm calling on behalf of {user_name} about the {vehicle_title} "
        f"you have listed{dealer_part}. "
        f"They'd love to come in for a test drive on {preferred_date} "
        f"around {preferred_time}. Would that work?"
    )


def build_test_drive_summary_prompt(
    vehicle_title: str,
    preferred_date: str,
    preferred_time: str,
    transcript_text: str,
) -> str:
    return f"""\
You are analyzing a short phone call transcript where someone tried to \
schedule a test drive for a {vehicle_title}.

The caller requested: {preferred_date} at {preferred_time}.

TRANSCRIPT:
{transcript_text}

Extract the following as JSON (and nothing else):
{{
  "confirmed": true/false,
  "scheduled_date": "the confirmed date or null",
  "scheduled_time": "the confirmed time or null",
  "dealer_notes": "any relevant notes from the dealer (1-2 sentences)"
}}

If the dealer confirmed the exact requested time, set confirmed=true and use that date/time.
If the dealer suggested an alternative and the caller accepted, set confirmed=true with the alternative.
If no time was agreed, set confirmed=false and put any suggested alternatives in dealer_notes.
Return ONLY the JSON object, no markdown fences.
"""
