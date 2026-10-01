"""Request/response models for document upload and inspection."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class PasteTextRequest(BaseModel):
    text: str = Field(..., min_length=40, max_length=200_000)
    name: Optional[str] = Field(default=None, max_length=120)

    @field_validator("text")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Text can't be empty.")
        return value


class PipelineStage(BaseModel):
    stage: str
    detail: str


class UploadResponse(BaseModel):
    session_id: str
    doc_id: str
    doc_type: str
    doc_name: str
    source_format: str
    page_count: int
    char_count: int
    chunk_count: int
    sections: List[str]
    elapsed_ms: int
    pipeline: List[PipelineStage]
    embedding_model: str
    vector_backend: str
    pages_are_synthetic: bool


class ChunkOut(BaseModel):
    chunk_id: str
    doc_type: str
    doc_name: str
    section: str
    page: int
    chunk_index: int
    text: str
    char_start: int
    char_end: int


class DocumentDetail(BaseModel):
    doc_id: str
    doc_type: str
    name: str
    source_format: str
    page_count: int
    char_count: int
    chunk_count: int
    sections: List[str]
    text: str


class SampleDocument(BaseModel):
    id: str
    label: str
    doc_type: str
    description: str
    preview: str


class LoadSampleRequest(BaseModel):
    resume_id: Optional[str] = None
    jd_id: Optional[str] = None
