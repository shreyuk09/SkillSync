"""Chat request/response models."""

from typing import Any, Dict, List

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)
    remember: bool = True


class ChatSource(BaseModel):
    ref: str
    chunk_id: str
    doc_type: str
    doc_name: str
    section: str
    page: int
    score: float
    citation: str
    text: str


class RetrievalStep(BaseModel):
    ref: str
    citation: str
    score: float
    chunk_id: str


class ChatResponse(BaseModel):
    answer: str
    found_answer: bool
    # True when part of the answer came from general knowledge rather than the
    # uploaded documents. The UI uses it to caption the reply.
    used_general_knowledge: bool = False
    sources: List[ChatSource] = Field(default_factory=list)
    follow_ups: List[str] = Field(default_factory=list)
    retrieval: List[RetrievalStep] = Field(default_factory=list)


class ChatMessage(BaseModel):
    role: str
    content: str
    sources: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: str


class ChatHistoryResponse(BaseModel):
    messages: List[ChatMessage] = Field(default_factory=list)
    suggested: List[str] = Field(default_factory=list)
