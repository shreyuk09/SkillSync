"""Request models for the analysis endpoints.

Analysis responses are deliberately returned as plain dictionaries: their shape
is defined by the JSON Schemas in `rag/prompts.py`, which are the single source
of truth. Duplicating those shapes as Pydantic models would mean maintaining
the same structure twice.
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field


class DecisionRequest(BaseModel):
    suggestion_id: str = Field(..., min_length=1, max_length=64)
    decision: Literal["accepted", "rejected", "pending"]


class InterviewRequest(BaseModel):
    focus: Optional[str] = Field(default=None, max_length=200)
    refresh: bool = False


class RoadmapRequest(BaseModel):
    weeks: int = Field(default=0, ge=0, le=12)
    refresh: bool = False


class SearchRequest(BaseModel):
    """Direct access to the retriever -- used by the 'RAG Inspector' panel."""

    query: str = Field(..., min_length=1, max_length=500)
    top_k: int = Field(default=6, ge=1, le=20)
    doc_type: Optional[Literal["resume", "jd"]] = None
