"""Shared response models."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    code: str
    message: str
    hint: Optional[str] = None


class ErrorResponse(BaseModel):
    error: ErrorDetail


class RagStatus(BaseModel):
    """What the RAG stack is actually running -- surfaced in the UI footer."""

    embedding_provider: str
    embedding_model: str
    embedding_dimension: int
    semantic_embeddings: bool
    vector_store: str
    llm_provider: str
    llm_model: str
    llm_configured: bool
    chunk_size: int
    chunk_overlap: int
    retrieval_top_k: int


class HealthResponse(BaseModel):
    status: str
    version: str
    rag: RagStatus
    warnings: List[str] = Field(default_factory=list)


class SessionResponse(BaseModel):
    session_id: str
    created: bool = True


class SessionStatus(BaseModel):
    session_id: str
    has_resume: bool
    has_jd: bool
    ready: bool
    chunk_count: int
    documents: List[Dict[str, Any]] = Field(default_factory=list)
    available_analyses: List[str] = Field(default_factory=list)


class MessageResponse(BaseModel):
    ok: bool = True
    message: str = ""
