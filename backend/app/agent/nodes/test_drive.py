"""Node: book_test_drive -- books a test drive using the booking tool."""

from langchain_core.messages import AIMessage

from app.agent.state import AgentState
from app.agent.tools.booking_tools import book_test_drive_sms


def book_test_drive(state: AgentState) -> dict:
    """Book a test drive for a selected vehicle via SMS to the dealer.

    Expects `test_drive_request` in the state (injected by the API layer
    when the user submits the booking form).
    """
    vehicles = state.get("vehicles", [])
    final_top3 = state.get("final_top3", [])
    bookings = list(state.get("test_drive_bookings", []))

    # The API layer injects a pending request into test_drive_bookings
    # with status="pending_send".  We find it and actually send the SMS.
    pending = [b for b in bookings if b.get("status") == "pending_send"]

    if not pending:
        return {
            "current_phase": "dashboard",
            "messages": [AIMessage(content="No pending test drive to book.")],
        }

    for booking in pending:
        vehicle_id = booking.get("vehicle_id", "")
        vehicle = next(
            (v for v in vehicles if v.get("vehicle_id") == vehicle_id),
            None,
        )
        if not vehicle:
            booking["status"] = "failed"
            booking["error"] = "Vehicle not found"
            continue

        result = book_test_drive_sms.invoke({
            "phone": vehicle.get("dealer_phone", ""),
            "vehicle_id": vehicle_id,
            "vehicle_title": vehicle.get("title", "Vehicle"),
            "date": booking.get("date", ""),
            "time": booking.get("time", ""),
            "user_name": booking.get("user_name", "Customer"),
        })

        booking["status"] = result.get("status", "failed")
        booking["booking_id"] = result.get("booking_id", "")

    return {
        "test_drive_bookings": bookings,
        "current_phase": "dashboard",
        "messages": [AIMessage(content=f"Processed {len(pending)} test drive booking(s).")],
    }
