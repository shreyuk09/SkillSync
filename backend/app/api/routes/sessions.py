"""Session lifecycle.

A session is one workspace: one resume + one job description + everything
derived from them. Creating a session is free and requires no account. Deleting
one removes every trace, including the vectors.
"""

from fastapi import APIRouter, status

from app.api.deps import SessionDep, SettingsDep, StoreDep
from app.rag.vector_store import get_vector_store
from app.schemas.common import MessageResponse, SessionResponse, SessionStatus

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
def create_session(store: StoreDep) -> SessionResponse:
    return SessionResponse(session_id=store.create_session())


@router.get("/{session_id}", response_model=SessionStatus)
def get_session(session_id: SessionDep, store: StoreDep) -> SessionStatus:
    documents = store.list_documents(session_id)
    has_resume = any(document["doc_type"] == "resume" for document in documents)
    has_jd = any(document["doc_type"] == "jd" for document in documents)

    return SessionStatus(
        session_id=session_id,
        has_resume=has_resume,
        has_jd=has_jd,
        ready=has_resume and has_jd,
        chunk_count=store.count_chunks(session_id),
        documents=[
            {
                "doc_id": document["id"],
                "doc_type": document["doc_type"],
                "name": document["name"],
                "format": document["source_format"],
                "pages": document["page_count"],
                "chunks": document["chunk_count"],
                "sections": document["sections"],
                "characters": document["char_count"],
            }
            for document in documents
        ],
        available_analyses=store.list_analysis_kinds(session_id),
    )


@router.delete("/{session_id}", response_model=MessageResponse)
def delete_session(
    session_id: SessionDep, store: StoreDep, settings: SettingsDep
) -> MessageResponse:
    get_vector_store(settings).delete_session(session_id)
    store.delete_session(session_id)
    return MessageResponse(message="Session and all associated data deleted.")
