"""Node: chat_agent -- LLM-driven preference refinement via conversation."""

import json

from langchain_core.messages import AIMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.agent.state import AgentState
from app.agent.prompts.chat_system import CHAT_SYSTEM_PROMPT
from app.config import get_settings


def chat_agent(state: AgentState) -> dict:
    """Invoke the LLM to refine preferences through conversation.

    Reads the current messages, sends them with a system prompt, and parses
    the structured JSON reply to extract updated_filters and readiness.
    """
    settings = get_settings()
    preferences = state.get("preferences", {})
    additional_filters = state.get("additional_filters", {})

    system_text = CHAT_SYSTEM_PROMPT.format(
        preferences=json.dumps(preferences, indent=2),
        additional_filters=json.dumps(additional_filters, indent=2),
    )

    if not settings.openai_api_key or settings.openai_api_key.startswith("sk-your"):
        return _stub_reply(state)

    llm = ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        temperature=0.7,
        model_kwargs={"response_format": {"type": "json_object"}},
    )

    conversation = [SystemMessage(content=system_text)] + list(state.get("messages", []))

    response = llm.invoke(conversation)
    raw_content = response.content

    try:
        parsed = json.loads(raw_content)
    except json.JSONDecodeError:
        parsed = {
            "reply": raw_content,
            "updated_filters": None,
            "is_ready_to_search": False,
        }

    reply_text = parsed.get("reply", raw_content)
    new_filters = parsed.get("updated_filters")
    is_ready = parsed.get("is_ready_to_search", False)

    merged_filters = {**additional_filters}
    if new_filters and isinstance(new_filters, dict):
        merged_filters.update(new_filters)

    return {
        "messages": [AIMessage(content=reply_text)],
        "additional_filters": merged_filters,
        "is_ready_to_search": bool(is_ready),
        "current_phase": "search" if is_ready else "chat",
    }


def _stub_reply(state: AgentState) -> dict:
    """Fallback when no OpenAI key is configured."""
    additional_filters = state.get("additional_filters", {})
    messages = state.get("messages", [])

    has_user_messages = any(
        getattr(m, "type", None) == "human" for m in messages
    )

    if not has_user_messages:
        reply = (
            "I'd love to help refine your search! "
            "What color do you prefer? Any must-have features like sunroof or leather seats? "
            "(Note: running in stub mode -- no OpenAI key configured)"
        )
    else:
        reply = (
            "Thanks for sharing! I've noted your preferences. "
            "I think I have enough to start searching. Let me know when you're ready! "
            "(Stub mode)"
        )

    return {
        "messages": [AIMessage(content=reply)],
        "additional_filters": additional_filters,
        "is_ready_to_search": has_user_messages,
        "current_phase": "search" if has_user_messages else "chat",
    }
