"""Node: auto_shortlist_top4 -- picks the top 4 vehicles by score."""

from langchain_core.messages import AIMessage

from app.agent.state import AgentState
from app.services.scoring_service import pick_top_n


def auto_shortlist(state: AgentState) -> dict:
    """Select top 4 vehicles and store their IDs in the shortlist."""
    vehicles = state.get("vehicles", [])

    if not vehicles:
        return {
            "shortlist_ids": [],
            "current_phase": "no_results",
            "messages": [AIMessage(content="No vehicles to shortlist.")],
        }

    top4 = pick_top_n(vehicles, n=4)
    shortlist_ids = [v["vehicle_id"] for v in top4]

    summary_lines = [f"  {i+1}. {v['title']} - ${v['price']:,.0f} (score: {v['overall_score']})"
                     for i, v in enumerate(top4)]
    summary = "Top 4 shortlisted vehicles:\n" + "\n".join(summary_lines)

    return {
        "shortlist_ids": shortlist_ids,
        "confirmed_shortlist": False,
        "current_phase": "confirm_shortlist",
        "messages": [AIMessage(content=summary)],
    }
