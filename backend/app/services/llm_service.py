"""OpenAI LLM integration for the conversational agent."""

from app.config import get_settings

SYSTEM_PROMPT = """You are a helpful car-buying assistant. The user has already filled out basic preferences.
Your job is to gather additional details that will help find the perfect car.
Ask about things like: preferred color, must-have features, deal-breakers, 
fuel type preference, transmission, seats, cargo space, etc.

When you have enough info, set is_ready_to_search to true.

Always respond with valid JSON:
{
  "reply": "your message to the user",
  "updated_filters": {"key": "value"} or null,
  "is_ready_to_search": false
}"""


async def get_chat_reply(
    preferences: dict,
    additional_filters: dict,
    history: list[tuple[str, str]],
) -> dict:
    """Get a reply from the LLM given chat history and current preferences.

    Returns dict with keys: reply, updated_filters, is_ready_to_search.
    """
    settings = get_settings()

    if not settings.openai_api_key:
        # Fallback stub when API key not configured
        return {
            "reply": (
                "I'd love to help refine your search! "
                "Could you tell me about any color preference or must-have features? "
                "(Note: OpenAI key not configured -- using stub response)"
            ),
            "updated_filters": None,
            "is_ready_to_search": False,
        }

    import openai

    client = openai.AsyncOpenAI(api_key=settings.openai_api_key)

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.append({
        "role": "system",
        "content": f"Current preferences: {preferences}\nAdditional filters: {additional_filters}",
    })
    for role, content in history:
        messages.append({"role": role, "content": content})

    response = await client.chat.completions.create(
        model=settings.openai_model,
        messages=messages,
        response_format={"type": "json_object"},
        temperature=0.7,
    )

    import json

    raw = response.choices[0].message.content
    return json.loads(raw)
