"""Node: chat_agent -- LLM-driven preference refinement via conversation."""

import json

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.agent.state import AgentState
from app.agent.prompts.chat_system import CHAT_SYSTEM_PROMPT
from app.config import get_settings
from app.services.bedrock_chat_service import has_bedrock_configured, invoke_converse_sync
from app.utils import parse_json_from_llm


def _messages_to_bedrock(messages: list) -> list[dict]:
    """Convert LangChain messages to Bedrock Converse format."""
    out = []
    for m in messages:
        role = "user"
        if isinstance(m, HumanMessage):
            role = "user"
        elif isinstance(m, AIMessage):
            role = "assistant"
        else:
            continue
        content = getattr(m, "content", "") or ""
        out.append({"role": role, "content": content})
    return out


def chat_agent(state: AgentState) -> dict:
    """Invoke the LLM to refine preferences through conversation.

    Uses Amazon Bedrock (DeepSeek). Reads current messages, sends with system prompt,
    parses structured JSON reply for updated_filters and readiness.
    """
    settings = get_settings()
    preferences = state.get("preferences", {})
    additional_filters = state.get("additional_filters", {})

    system_text = CHAT_SYSTEM_PROMPT.format(
        preferences=json.dumps(preferences, indent=2),
        additional_filters=json.dumps(additional_filters, indent=2),
    )

    if not has_bedrock_configured():
        return _stub_reply(state)

    conversation = list(state.get("messages", []))
    bedrock_messages = _messages_to_bedrock(conversation)
    if not bedrock_messages:
        bedrock_messages = [{"role": "user", "content": "Hi, I'm ready to refine my search."}]

    raw_content = invoke_converse_sync(
        bedrock_messages,
        system=system_text,
        temperature=0.7,
        max_tokens=2048,
    )

    try:
        parsed = parse_json_from_llm(raw_content)
    except (json.JSONDecodeError, ValueError):
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
    """Fallback when Bedrock is not configured."""
    additional_filters = state.get("additional_filters", {})
    messages = state.get("messages", [])

    has_user_messages = any(
        getattr(m, "type", None) == "human" for m in messages
    )

    if not has_user_messages:
        reply = (
            "I'd love to help refine your search! "
            "What color do you prefer? Any must-have features like sunroof or leather seats? "
            "(Note: running in stub mode -- Bedrock not configured)"
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
