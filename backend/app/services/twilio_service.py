"""Twilio SMS integration for dealership communication."""

from app.config import get_settings

MESSAGE_TEMPLATES = {
    "inquiry": (
        "Hi, I'm interested in the {title} listed at ${price:,.0f}. "
        "Is it still available? I'd love to learn more."
    ),
    "negotiate": (
        "Hi, I'm looking at the {title} listed at ${price:,.0f}. "
        "Would you consider a lower offer? I'm a serious buyer."
    ),
    "test_drive": (
        "Hi, I'd like to schedule a test drive for the {title}. "
        "Could you let me know available times this week?"
    ),
}


async def send_sms(dealer_phone: str, vehicle: dict, template: str) -> str:
    """Send an SMS to a dealer about a vehicle.

    Returns the message body that was sent.
    """
    settings = get_settings()

    body = MESSAGE_TEMPLATES.get(template, MESSAGE_TEMPLATES["inquiry"]).format(
        title=vehicle.get("title", "vehicle"),
        price=vehicle.get("price", 0),
    )

    if not settings.twilio_account_sid:
        # Stub mode -- just return the message without sending
        return f"[STUB] {body}"

    from twilio.rest import Client

    client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
    message = client.messages.create(
        body=body,
        from_=settings.twilio_phone_number,
        to=dealer_phone,
    )
    return body
