from fastapi import APIRouter
from pydantic import ValidationError

from app.api.sessions import get_session_or_404
from app.models.documents import ChatMessageDocument, UserDocument
from app.models.schemas import (
    ChatRequest,
    ChatResponse,
    ChatHistoryResponse,
    ChatMessageOut,
    UserRequirements,
)
from app.models.user_requirements import (
    get_user_requirements,
    update_user_requirements,
    merge_filters_into_requirements,
)
from app.services.llm_service import get_chat_reply

router = APIRouter(prefix="/api/sessions/{session_id}/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def send_chat_message(session_id: str, body: ChatRequest):
    """Send a message to the conversational AI agent. Fills/updates user requirements in MongoDB."""
    session = await get_session_or_404(session_id)

    # Ensure session has a user (create one if missing, e.g. legacy sessions)
    if not session.user_id:
        user = UserDocument()
        await user.insert()
        session.user_id = user.user_id
        await session.save()
    user_id = session.user_id

    # Load current requirements from MongoDB (or use defaults)
    current_req = await get_user_requirements(user_id)
    if current_req is None:
        current_req = UserRequirements()
    preferences_dict = current_req.model_dump()
    additional_filters = session.additional_filters or {}

    # Persist user message
    user_msg = ChatMessageDocument(
        session_id=session_id,
        role="user",
        content=body.message,
    )
    await user_msg.insert()

    # Get AI reply (LLM sees current requirements)
    history = await ChatMessageDocument.find(
        ChatMessageDocument.session_id == session_id
    ).sort("+timestamp").to_list()

    reply_data = await get_chat_reply(
        preferences=preferences_dict,
        additional_filters=additional_filters,
        history=[(m.role, m.content) for m in history],
    )

    # Merge LLM updated_filters into UserRequirements and save to MongoDB
    updated_filters = reply_data.get("updated_filters") or {}
    try:
        merged_req = merge_filters_into_requirements(current_req, updated_filters)
        await update_user_requirements(user_id, merged_req)
        merged_dict = merged_req.model_dump()
        session.preferences = merged_dict
        session.additional_filters = {**additional_filters, **updated_filters}
        await session.save()
    except ValidationError:
        # LLM returned invalid values; keep current requirements in DB, only update session filters
        session.preferences = current_req.model_dump()
        session.additional_filters = {**additional_filters, **updated_filters}
        await session.save()

    # Persist assistant message
    assistant_msg = ChatMessageDocument(
        session_id=session_id,
        role="assistant",
        content=reply_data["reply"],
        updated_filters=updated_filters,
    )
    await assistant_msg.insert()

    return ChatResponse(
        reply=reply_data["reply"],
        updated_filters=updated_filters,
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
