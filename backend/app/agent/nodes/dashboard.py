"""Node: present_dashboard -- formats state into the dashboard response."""

from langchain_core.messages import AIMessage

from app.agent.state import AgentState


def present_dashboard(state: AgentState) -> dict:
    """Format the current state into a dashboard-ready summary.

    This is a pure function node -- no LLM call, just data transformation.
    The actual API response is built in the FastAPI route by reading graph
    state; this node just sets the phase and produces a summary message.
    """
    vehicles = state.get("vehicles", [])
    final_top3 = state.get("final_top3", [])
    communications = state.get("communications", [])
    test_drive_bookings = state.get("test_drive_bookings", [])

    top3_vehicles = [v for v in vehicles if v.get("vehicle_id") in final_top3]

    lines = ["Dashboard ready. Final picks:"]
    for i, v in enumerate(top3_vehicles):
        comm_count = sum(
            1 for c in communications
            if c.get("args", {}).get("phone") == v.get("dealer_phone")
        )
        lines.append(
            f"  {i+1}. {v.get('title', 'N/A')} - ${v.get('price', 0):,.0f} "
            f"({comm_count} contacts)"
        )

    if test_drive_bookings:
        lines.append(f"\nTest drives booked: {len(test_drive_bookings)}")

    return {
        "current_phase": "dashboard",
        "messages": [AIMessage(content="\n".join(lines))],
    }
