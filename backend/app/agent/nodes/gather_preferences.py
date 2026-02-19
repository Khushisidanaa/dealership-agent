"""Node: gather_preferences -- validates and stores static questionnaire data."""

from langchain_core.messages import SystemMessage

from app.agent.state import AgentState


def gather_preferences(state: AgentState) -> dict:
    """Pure function node. Validates that preferences exist and sets the
    initial phase.  Returns a partial state update."""
    preferences = state.get("preferences", {})

    if not preferences.get("make") or not preferences.get("zip_code"):
        return {
            "current_phase": "error",
            "messages": [
                SystemMessage(content="Missing required preferences: make and zip_code are required.")
            ],
        }

    return {
        "current_phase": "chat",
        "is_ready_to_search": False,
        "additional_filters": state.get("additional_filters") or {},
        "messages": [
            SystemMessage(
                content=(
                    f"Session started. User is looking for a "
                    f"{preferences.get('make', '')} {preferences.get('model', '')} "
                    f"near {preferences.get('zip_code', '')}."
                )
            )
        ],
    }
