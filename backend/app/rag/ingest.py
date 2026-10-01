"""Ingestion -- runs stages 1 through 6 end to end.

    bytes / pasted text
        -> extract   (text + page map)
        -> clean     (normalise, keep offsets valid)
        -> section   (Skills, Projects, Responsibilities, ...)
        -> chunk     (overlapping, metadata-rich)
        -> embed     (one vector per chunk)
        -> store     (SQLite for the text, vector DB for the vectors)

This is the single place a document enters the system. Everything downstream
(match scoring, chat, interview prep) reads from what this function wrote.
"""

import time
import uuid
from dataclasses import dataclass
from typing import List, Optional

from app.core.config import Settings
from app.core.logging import get_logger
from app.models.store import Store
from app.rag.chunking import Chunk, chunk_document
from app.rag.cleaning import clean_document
from app.rag.embeddings import get_embedder
from app.rag.extraction import ExtractedDocument, extract_document, extract_from_plain_text
from app.rag.sectioning import Section, detect_sections, section_names
from app.rag.vector_store import get_vector_store

logger = get_logger(__name__)


@dataclass
class IngestionResult:
    doc_id: str
    doc_type: str
    doc_name: str
    source_format: str
    page_count: int
    char_count: int
    chunk_count: int
    sections: List[str]
    text: str
    chunks: List[Chunk]
    embedding_model: str
    vector_backend: str
    elapsed_ms: int
    pages_are_synthetic: bool

    def pipeline_trace(self) -> List[dict]:
        """A human-readable trace of what the pipeline did.

        Surfaced in the UI so the RAG process is visible rather than magic.
        """
        return [
            {
                "stage": "Extraction",
                "detail": f"Read {self.char_count:,} characters from {self.page_count} "
                          f"page(s) of {self.source_format.upper()}",
            },
            {"stage": "Cleaning", "detail": "Normalised whitespace, bullets, hyphenation and headers"},
            {
                "stage": "Sectioning",
                "detail": f"Detected {len(self.sections)} sections: {', '.join(self.sections)}",
            },
            {"stage": "Chunking", "detail": f"Split into {self.chunk_count} overlapping chunks"},
            {"stage": "Embedding", "detail": f"Encoded each chunk with {self.embedding_model}"},
            {"stage": "Indexing", "detail": f"Stored {self.chunk_count} vectors in {self.vector_backend}"},
        ]


def _ingest_extracted(
    document: ExtractedDocument,
    *,
    session_id: str,
    doc_type: str,
    doc_name: str,
    settings: Settings,
    store: Store,
) -> IngestionResult:
    started = time.time()

    # STAGE 2 -- clean (rebuilds the page map so offsets stay correct)
    document = clean_document(document)

    # STAGE 3 -- detect sections
    sections: List[Section] = detect_sections(document.text, doc_type)

    # STAGE 4 -- chunk
    doc_id = f"{doc_type}-{uuid.uuid4().hex[:8]}"
    chunks = chunk_document(
        document,
        sections,
        doc_id=doc_id,
        doc_type=doc_type,
        doc_name=doc_name,
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )

    # STAGE 5 -- embed
    embedder = get_embedder(settings)
    vectors = embedder.embed_documents([chunk.embed_text for chunk in chunks])

    # STAGE 6 -- store. A session holds exactly one resume and one job
    # description, so the previous document of this type is removed first --
    # otherwise its chunks would linger and be retrieved alongside the new
    # document's.
    vector_store = get_vector_store(settings)
    for old_doc_id in store.delete_documents_of_type(session_id, doc_type):
        vector_store.delete_document(session_id, old_doc_id)

    vector_store.add(session_id, chunks, vectors)
    store.save_chunks(session_id, chunks)
    store.save_document(
        session_id=session_id,
        doc_id=doc_id,
        doc_type=doc_type,
        name=doc_name,
        source_format=document.source_format,
        page_count=document.page_count,
        char_count=len(document.text),
        chunk_count=len(chunks),
        sections=section_names(sections),
        text=document.text,
    )

    # Every cached analysis describes the document that was just replaced, so
    # it is discarded outright. The next request recomputes from scratch and
    # nothing from the previous run can survive into the new one.
    store.clear_analyses(session_id)

    elapsed_ms = int((time.time() - started) * 1000)
    logger.info(
        "Ingested %s '%s' for session %s: %d chunks in %d ms",
        doc_type, doc_name, session_id, len(chunks), elapsed_ms,
    )

    return IngestionResult(
        doc_id=doc_id,
        doc_type=doc_type,
        doc_name=doc_name,
        source_format=document.source_format,
        page_count=document.page_count,
        char_count=len(document.text),
        chunk_count=len(chunks),
        sections=section_names(sections),
        text=document.text,
        chunks=chunks,
        embedding_model=embedder.display_name,
        vector_backend=vector_store.display_name,
        elapsed_ms=elapsed_ms,
        pages_are_synthetic=document.pages_are_synthetic,
    )


def ingest_file(
    content: bytes,
    extension: str,
    filename: str,
    *,
    session_id: str,
    doc_type: str,
    settings: Settings,
    store: Store,
) -> IngestionResult:
    """Ingest an uploaded file. `content` never touches the filesystem."""
    document = extract_document(content, extension)  # STAGE 1
    return _ingest_extracted(
        document,
        session_id=session_id,
        doc_type=doc_type,
        doc_name=filename,
        settings=settings,
        store=store,
    )


def ingest_text(
    text: str,
    *,
    session_id: str,
    doc_type: str,
    settings: Settings,
    store: Store,
    doc_name: Optional[str] = None,
) -> IngestionResult:
    """Ingest text pasted directly into the UI."""
    document = extract_from_plain_text(text)  # STAGE 1
    return _ingest_extracted(
        document,
        session_id=session_id,
        doc_type=doc_type,
        doc_name=doc_name or ("Pasted job description" if doc_type == "jd" else "Pasted resume"),
        settings=settings,
        store=store,
    )
