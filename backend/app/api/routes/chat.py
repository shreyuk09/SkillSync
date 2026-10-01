"""RAG chatbot endpoints."""

from fastapi import APIRouter

from app.api.deps import SessionDep, SettingsDep, StoreDep
from app.schemas.chat import ChatHistoryResponse, ChatRequest, ChatResponse
from app.schemas.common import MessageResponse
from app.services import chat as chat_service

router = APIRouter(prefix="/sessions/{session_id}/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
def ask(
    session_id: SessionDep,
    payload: ChatRequest,
    settings: SettingsDep,
    store: StoreDep,
) -> ChatResponse:
    """Ask a question. Retrieval happens first; the answer cites its sources."""
    result = chat_service.ask(
        session_id, payload.question, settings, store, remember=payload.remember
    )
    return ChatResponse(**result)


@router.get("", response_model=ChatHistoryResponse)
def history(session_id: SessionDep, store: StoreDep) -> ChatHistoryResponse:
    return ChatHistoryResponse(
        messages=chat_service.history(session_id, store),
        suggested=chat_service.SUGGESTED_QUESTIONS,
    )


@router.delete("", response_model=MessageResponse)
def clear(session_id: SessionDep, store: StoreDep) -> MessageResponse:
    store.clear_chat(session_id)
    return MessageResponse(message="Conversation cleared.")
