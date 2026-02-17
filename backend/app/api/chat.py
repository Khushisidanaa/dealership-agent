from fastapi import APIRouter

from app.api.sessions import get_session_or_404
from app.models.documents import ChatMessageDocument
from app.models.schemas import (
    ChatRequest,
    ChatResponse,
    ChatHistoryResponse,
    ChatMessageOut,
)
from app.services.llm_service import get_chat_reply

router = APIRouter(prefix="/api/sessions/{session_id}/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def send_chat_message(session_id: str, body: ChatRequest):
    """Send a message to the conversational AI agent."""
    session = await get_session_or_404(session_id)

    # Persist user message
    user_msg = ChatMessageDocument(
        session_id=session_id,
        role="user",
        content=body.message,
    )
    await user_msg.insert()

    # Get AI reply
    history = await ChatMessageDocument.find(
        ChatMessageDocument.session_id == session_id
    ).sort("+timestamp").to_list()

    reply_data = await get_chat_reply(
        preferences=session.preferences or {},
        additional_filters=session.additional_filters or {},
        history=[(m.role, m.content) for m in history],
    )

    # Persist assistant message
    assistant_msg = ChatMessageDocument(
        session_id=session_id,
        role="assistant",
        content=reply_data["reply"],
        updated_filters=reply_data.get("updated_filters"),
    )
    await assistant_msg.insert()

    # Merge updated filters into session
    if reply_data.get("updated_filters"):
        merged = {**(session.additional_filters or {}), **reply_data["updated_filters"]}
        session.additional_filters = merged
        await session.save()

    return ChatResponse(
        reply=reply_data["reply"],
        updated_filters=reply_data.get("updated_filters"),
        is_ready_to_search=reply_data.get("is_ready_to_search", False),
    )


@router.get("/history", response_model=ChatHistoryResponse)
async def get_chat_history(session_id: str):
    """Retrieve full chat history for a session."""
    await get_session_or_404(session_id)

    messages = await ChatMessageDocument.find(
        ChatMessageDocument.session_id == session_id
    ).sort("+timestamp").to_list()

    return ChatHistoryResponse(
        messages=[
            ChatMessageOut(role=m.role, content=m.content, timestamp=m.timestamp)
            for m in messages
        ]
    )
