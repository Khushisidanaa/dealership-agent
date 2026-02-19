"""LangGraph StateGraph definition for the dealership agent.

This module builds and compiles the full agent graph.  The compiled graph
is used by the FastAPI endpoints to invoke / resume the workflow.

Graph flow:
  START -> gather_preferences -> chat_agent -> [ready?]
    no  -> INTERRUPT (wait for user message) -> chat_agent
    yes -> web_search -> [has results?]
      no  -> web_search (retry)
      yes -> analyze_and_score -> auto_shortlist -> INTERRUPT (confirm)
        -> contact_dealers -> final_ranking -> present_dashboard
          -> INTERRUPT (user action: book test drive / done)
            book -> book_test_drive -> present_dashboard
            done -> END
"""

from langgraph.graph import StateGraph, END

from app.agent.state import AgentState
from app.agent.nodes.gather_preferences import gather_preferences
from app.agent.nodes.chat_agent import chat_agent
from app.agent.nodes.web_search import web_search
from app.agent.nodes.analyze_score import analyze_and_score
from app.agent.nodes.shortlist import auto_shortlist
from app.agent.nodes.contact_dealers import contact_dealers
from app.agent.nodes.summarize_calls import summarize_calls
from app.agent.nodes.final_ranking import final_ranking
from app.agent.nodes.dashboard import present_dashboard
from app.agent.nodes.test_drive import book_test_drive


# ---------------------------------------------------------------------------
# Routing functions (conditional edges)
# ---------------------------------------------------------------------------

def _route_after_chat(state: AgentState) -> str:
    """After chat_agent: go to search if ready, otherwise interrupt for user input."""
    if state.get("is_ready_to_search"):
        return "web_search"
    return "wait_for_user"


def _route_after_search(state: AgentState) -> str:
    """After web_search: go to analyze if results exist, retry, or bail."""
    phase = state.get("current_phase", "")
    if phase == "analyze":
        return "analyze_and_score"
    if phase == "search" and state.get("retry_count", 0) < 3:
        return "web_search"
    return "analyze_and_score"


def _route_after_dashboard(state: AgentState) -> str:
    """After present_dashboard: check if there is a pending test drive to book."""
    bookings = state.get("test_drive_bookings", [])
    has_pending = any(b.get("status") == "pending_send" for b in bookings)
    if has_pending:
        return "book_test_drive"
    return "wait_for_action"


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------

def build_graph() -> StateGraph:
    """Construct the StateGraph with all nodes and edges."""
    builder = StateGraph(AgentState)

    # -- add nodes --
    builder.add_node("gather_preferences", gather_preferences)
    builder.add_node("chat_agent", chat_agent)
    builder.add_node("web_search", web_search)
    builder.add_node("analyze_and_score", analyze_and_score)
    builder.add_node("auto_shortlist", auto_shortlist)
    builder.add_node("contact_dealers", contact_dealers)
    builder.add_node("summarize_calls", summarize_calls)
    builder.add_node("final_ranking", final_ranking)
    builder.add_node("present_dashboard", present_dashboard)
    builder.add_node("book_test_drive", book_test_drive)

    # -- entry point --
    builder.set_entry_point("gather_preferences")

    # -- edges --

    # gather_preferences -> chat_agent (always)
    builder.add_edge("gather_preferences", "chat_agent")

    # chat_agent -> conditional: search or wait
    builder.add_conditional_edges(
        "chat_agent",
        _route_after_chat,
        {
            "web_search": "web_search",
            "wait_for_user": END,  # graph pauses; API resumes with user msg
        },
    )

    # web_search -> conditional: analyze or retry
    builder.add_conditional_edges(
        "web_search",
        _route_after_search,
        {
            "analyze_and_score": "analyze_and_score",
            "web_search": "web_search",
        },
    )

    # analyze -> shortlist -> END (interrupt for confirmation)
    builder.add_edge("analyze_and_score", "auto_shortlist")
    builder.add_edge("auto_shortlist", END)

    # After user confirms shortlist: call dealers -> summarize -> rank -> dashboard
    builder.add_edge("contact_dealers", "summarize_calls")
    builder.add_edge("summarize_calls", "final_ranking")
    builder.add_edge("final_ranking", "present_dashboard")

    # present_dashboard -> conditional: book test drive or wait
    builder.add_conditional_edges(
        "present_dashboard",
        _route_after_dashboard,
        {
            "book_test_drive": "book_test_drive",
            "wait_for_action": END,
        },
    )

    # book_test_drive loops back to dashboard
    builder.add_edge("book_test_drive", "present_dashboard")

    return builder


def compile_graph(checkpointer=None):
    """Build and compile the graph, optionally with a checkpointer.

    Returns a compiled graph that can be invoked/streamed.
    """
    builder = build_graph()
    return builder.compile(checkpointer=checkpointer)
