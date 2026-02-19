"""Central state schema for the LangGraph dealership agent."""

from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """Shared state that flows through every node in the graph.

    LangGraph passes a copy to each node; the node returns a partial dict
    with only the keys it wants to update.  The `messages` key uses the
    built-in `add_messages` reducer so new messages are appended (or
    merged by ID) rather than replaced.
    """

    # -- session --
    session_id: str

    # -- preferences (static questionnaire) --
    preferences: dict

    # -- additional filters (refined via chat) --
    additional_filters: dict

    # -- LLM conversation history --
    messages: Annotated[list[BaseMessage], add_messages]

    # -- chat readiness flag --
    is_ready_to_search: bool

    # -- search phase --
    search_queries: list[str]
    raw_search_results: list[dict]

    # -- scored vehicles --
    vehicles: list[dict]
    price_stats: dict

    # -- shortlist --
    shortlist_ids: list[str]
    confirmed_shortlist: bool

    # -- dealer communication --
    communications: list[dict]
    dealer_responses: list[dict]

    # -- structured call summaries (produced by summarize_calls node) --
    call_summaries: list[dict]

    # -- final output --
    final_top3: list[str]
    test_drive_bookings: list[dict]

    # -- control flow --
    current_phase: str
    retry_count: int
