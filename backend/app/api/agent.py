from __future__ import annotations

"""FastAPI routes that drive the LangGraph agent.

These endpoints invoke or resume the compiled graph.  The existing
'direct' routes (sessions, preferences, chat, search, etc.) still work
for backward compatibility, but this router provides the agent-driven
flow where a single graph orchestrates everything.

Endpoints:
  POST /api/agent/start          -- create session + submit prefs + get first chat msg
  POST /api/agent/{id}/chat      -- send user message, resume chat_agent node
  POST /api/agent/{id}/search    -- signal ready; runs search -> score -> shortlist
  POST /api/agent/{id}/confirm   -- confirm shortlist; runs contact -> rank -> dashboard
  POST /api/agent/{id}/testdrive -- book a test drive
  GET  /api/agent/{id}/state     -- read current graph state (for dashboard)
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage

from app.agent.checkpointer import get_checkpointer
from app.agent.graph import compile_graph
from app.models.documents import SessionDocument
from app.models.documents import new_uuid

router = APIRouter(prefix="/api/agent", tags=["agent"])


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class AgentStartRequest(BaseModel):
    make: str
    model: str = ""
    year_min: int = 2015
    year_max: int = 2026
    price_min: float = 0
    price_max: float = 100_000
    condition: str = "any"
    zip_code: str
    radius_miles: int = 50
    max_mileage: int | None = None


class AgentChatRequest(BaseModel):
    message: str


class AgentTestDriveRequest(BaseModel):
    vehicle_id: str
    date: str
    time: str
    user_name: str
    user_phone: str = ""


class AgentMessageOut(BaseModel):
    role: str
    content: str


class AgentResponse(BaseModel):
    session_id: str
    phase: str
    messages: list[AgentMessageOut] = Field(default_factory=list)
    vehicles: list[dict] = Field(default_factory=list)
    shortlist_ids: list[str] = Field(default_factory=list)
    final_top3: list[str] = Field(default_factory=list)
    price_stats: dict = Field(default_factory=dict)
    communications: list[dict] = Field(default_factory=list)
    call_summaries: list[dict] = Field(default_factory=list)
    test_drive_bookings: list[dict] = Field(default_factory=list)
    is_ready_to_search: bool = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _graph_config(session_id: str) -> dict:
    """Build the LangGraph config dict (thread_id = session_id)."""
    return {"configurable": {"thread_id": session_id, "checkpoint_ns": ""}}


def _state_to_response(session_id: str, state: dict) -> AgentResponse:
    """Convert raw graph state to a typed API response."""
    messages = []
    for m in state.get("messages", []):
        role = getattr(m, "type", "unknown")
        if role == "human":
            role = "user"
        elif role in ("ai", "AIMessage"):
            role = "assistant"
        elif role == "system":
            role = "system"
        content = getattr(m, "content", str(m))
        messages.append(AgentMessageOut(role=role, content=content))

    return AgentResponse(
        session_id=session_id,
        phase=state.get("current_phase", "unknown"),
        messages=messages,
        vehicles=state.get("vehicles", []),
        shortlist_ids=state.get("shortlist_ids", []),
        final_top3=state.get("final_top3", []),
        price_stats=state.get("price_stats", {}),
        communications=state.get("communications", []),
        call_summaries=state.get("call_summaries", []),
        test_drive_bookings=state.get("test_drive_bookings", []),
        is_ready_to_search=state.get("is_ready_to_search", False),
    )


async def _get_graph():
    """Get a compiled graph with the MongoDB checkpointer."""
    checkpointer = await get_checkpointer()
    return compile_graph(checkpointer=checkpointer)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/start", response_model=AgentResponse, status_code=201)
async def agent_start(body: AgentStartRequest):
    """Create a new session, submit preferences, and get the first chat message.

    This runs: gather_preferences -> chat_agent -> END (waits for user).
    """
    session = SessionDocument()
    await session.insert()
    session_id = session.session_id

    preferences = body.model_dump()
    initial_state = {
        "session_id": session_id,
        "preferences": preferences,
        "additional_filters": {},
        "messages": [],
        "is_ready_to_search": False,
        "search_queries": [],
        "raw_search_results": [],
        "vehicles": [],
        "price_stats": {},
        "shortlist_ids": [],
        "confirmed_shortlist": False,
        "communications": [],
        "dealer_responses": [],
        "call_summaries": [],
        "final_top3": [],
        "test_drive_bookings": [],
        "current_phase": "init",
        "retry_count": 0,
    }

    graph = await _get_graph()
    config = _graph_config(session_id)
    result = await graph.ainvoke(initial_state, config)

    # Persist preferences to session doc
    session.preferences = preferences
    session.status = "chat"
    await session.save()

    return _state_to_response(session_id, result)


@router.post("/{session_id}/chat", response_model=AgentResponse)
async def agent_chat(session_id: str, body: AgentChatRequest):
    """Send a user message. Resumes the graph from chat_agent.

    The graph runs chat_agent again, which either loops back to END
    (waiting for more input) or proceeds to web_search if ready.
    """
    graph = await _get_graph()
    config = _graph_config(session_id)

    # Get current checkpoint to read state
    checkpoint = await graph.checkpointer.aget(config)
    if not checkpoint:
        raise HTTPException(status_code=404, detail="Session not found in graph")

    state = checkpoint.get("channel_values", {})

    # Add the user's message and re-invoke from chat_agent
    updated = {
        **state,
        "messages": list(state.get("messages", [])) + [HumanMessage(content=body.message)],
        "current_phase": "chat",
    }

    result = await graph.ainvoke(updated, config)
    return _state_to_response(session_id, result)


@router.post("/{session_id}/search", response_model=AgentResponse)
async def agent_search(session_id: str):
    """Signal the agent to start searching.

    Forces is_ready_to_search=True and re-invokes from the beginning.
    The graph will skip through gather_preferences and chat_agent
    straight to web_search -> analyze -> shortlist -> END.
    """
    graph = await _get_graph()
    config = _graph_config(session_id)

    checkpoint = await graph.checkpointer.aget(config)
    if not checkpoint:
        raise HTTPException(status_code=404, detail="Session not found in graph")

    state = checkpoint.get("channel_values", {})

    updated = {
        **state,
        "is_ready_to_search": True,
        "current_phase": "search",
    }

    result = await graph.ainvoke(updated, config)
    return _state_to_response(session_id, result)


@router.post("/{session_id}/confirm", response_model=AgentResponse)
async def agent_confirm_shortlist(session_id: str):
    """Confirm the shortlist. Resumes the graph from contact_dealers.

    Runs: contact_dealers -> final_ranking -> present_dashboard -> END.
    """
    graph = await _get_graph()
    config = _graph_config(session_id)

    checkpoint = await graph.checkpointer.aget(config)
    if not checkpoint:
        raise HTTPException(status_code=404, detail="Session not found in graph")

    state = checkpoint.get("channel_values", {})

    if not state.get("shortlist_ids"):
        raise HTTPException(status_code=400, detail="No shortlist to confirm")

    # We need to invoke the sub-section of the graph starting from
    # contact_dealers.  We re-compile a mini-graph or just invoke
    # the nodes in sequence using the compiled graph's update mechanism.
    # The simplest approach: re-invoke with confirmed flag + entry adjustment.

    updated = {
        **state,
        "confirmed_shortlist": True,
        "current_phase": "contact",
    }

    from app.agent.nodes.contact_dealers import contact_dealers
    from app.agent.nodes.summarize_calls import summarize_calls
    from app.agent.nodes.final_ranking import final_ranking
    from app.agent.nodes.dashboard import present_dashboard

    contact_result = contact_dealers(updated)
    updated.update(contact_result)

    summary_result = summarize_calls(updated)
    updated.update(summary_result)

    rank_result = final_ranking(updated)
    updated.update(rank_result)

    dash_result = present_dashboard(updated)
    updated.update(dash_result)

    await graph.aupdate_state(config, updated)
    return _state_to_response(session_id, updated)


@router.post("/{session_id}/testdrive", response_model=AgentResponse)
async def agent_book_test_drive(session_id: str, body: AgentTestDriveRequest):
    """Book a test drive for a specific vehicle."""
    graph = await _get_graph()
    config = _graph_config(session_id)

    checkpoint = await graph.checkpointer.aget(config)
    if not checkpoint:
        raise HTTPException(status_code=404, detail="Session not found in graph")

    state = checkpoint.get("channel_values", {})

    bookings = list(state.get("test_drive_bookings", []))
    bookings.append({
        "vehicle_id": body.vehicle_id,
        "date": body.date,
        "time": body.time,
        "user_name": body.user_name,
        "user_phone": body.user_phone,
        "status": "pending_send",
    })

    updated = {**state, "test_drive_bookings": bookings}

    from app.agent.nodes.test_drive import book_test_drive
    from app.agent.nodes.dashboard import present_dashboard

    td_result = book_test_drive(updated)
    updated.update(td_result)

    dash_result = present_dashboard(updated)
    updated.update(dash_result)

    await graph.aupdate_state(config, updated)
    return _state_to_response(session_id, updated)


@router.get("/{session_id}/state", response_model=AgentResponse)
async def agent_get_state(session_id: str):
    """Read the current graph state for this session (used by the dashboard)."""
    graph = await _get_graph()
    config = _graph_config(session_id)

    checkpoint = await graph.checkpointer.aget(config)
    if not checkpoint:
        raise HTTPException(status_code=404, detail="Session not found in graph")

    state = checkpoint.get("channel_values", {})
    return _state_to_response(session_id, state)
