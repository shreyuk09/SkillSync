"""Document upload, inspection and raw retrieval.

Upload runs the whole ingestion pipeline synchronously and returns a trace of
what each stage did, which the UI shows as a live "RAG pipeline" panel.
"""

from typing import Literal, Optional

from fastapi import APIRouter, File, UploadFile
from fastapi.concurrency import run_in_threadpool

from app.api.deps import SessionDep, SettingsDep, StoreDep
from app.core.errors import (
    EmptyDocument,
    FileTooLarge,
    JobDescriptionMissing,
    ResumeMissing,
    SessionNotFound,
)
from app.rag.ingest import IngestionResult, ingest_file, ingest_text
from app.rag.retriever import get_retriever
from app.schemas.analysis import SearchRequest
from app.schemas.documents import (
    ChunkOut,
    DocumentDetail,
    PasteTextRequest,
    UploadResponse,
)
from app.utils.files import validate_upload

router = APIRouter(prefix="/sessions/{session_id}", tags=["documents"])

DocType = Literal["resume", "jd"]


def _to_response(session_id: str, result: IngestionResult) -> UploadResponse:
    return UploadResponse(
        session_id=session_id,
        doc_id=result.doc_id,
        doc_type=result.doc_type,
        doc_name=result.doc_name,
        source_format=result.source_format,
        page_count=result.page_count,
        char_count=result.char_count,
        chunk_count=result.chunk_count,
        sections=result.sections,
        elapsed_ms=result.elapsed_ms,
        pipeline=result.pipeline_trace(),
        embedding_model=result.embedding_model,
        vector_backend=result.vector_backend,
        pages_are_synthetic=result.pages_are_synthetic,
    )


async def _read_upload(file: UploadFile, settings) -> bytes:
    """Read an upload with a hard cap, so a huge file can't exhaust memory."""
    limit = settings.max_upload_bytes
    content = await file.read(limit + 1)
    if len(content) > limit:
        raise FileTooLarge(
            f"That file is larger than the {settings.max_upload_mb} MB limit.",
            hint="Compress the file or paste the text instead.",
        )
    return content


@router.post("/documents/{doc_type}/upload", response_model=UploadResponse)
async def upload_document(
    session_id: SessionDep,
    doc_type: DocType,
    settings: SettingsDep,
    store: StoreDep,
    file: UploadFile = File(...),
) -> UploadResponse:
    """Upload a resume or job description as PDF / DOCX / TXT / MD."""
    content = await _read_upload(file, settings)
    safe_name, extension = validate_upload(file.filename or "document", content, settings)

    # Ingestion is CPU-bound (parsing + embedding), so keep the event loop free.
    result = await run_in_threadpool(
        ingest_file,
        content,
        extension,
        safe_name,
        session_id=session_id,
        doc_type=doc_type,
        settings=settings,
        store=store,
    )
    return _to_response(session_id, result)


@router.post("/documents/{doc_type}/text", response_model=UploadResponse)
async def paste_document(
    session_id: SessionDep,
    doc_type: DocType,
    payload: PasteTextRequest,
    settings: SettingsDep,
    store: StoreDep,
) -> UploadResponse:
    """Submit a resume or job description as pasted text."""
    result = await run_in_threadpool(
        ingest_text,
        payload.text,
        session_id=session_id,
        doc_type=doc_type,
        settings=settings,
        store=store,
        doc_name=payload.name,
    )
    return _to_response(session_id, result)



@router.get("/documents/{doc_type}", response_model=DocumentDetail)
def get_document(session_id: SessionDep, doc_type: DocType, store: StoreDep) -> DocumentDetail:
    document = store.get_document(session_id, doc_type)
    if not document:
        raise ResumeMissing() if doc_type == "resume" else JobDescriptionMissing()
    return DocumentDetail(
        doc_id=document["id"],
        doc_type=document["doc_type"],
        name=document["name"],
        source_format=document["source_format"],
        page_count=document["page_count"],
        char_count=document["char_count"],
        chunk_count=document["chunk_count"],
        sections=document["sections"],
        text=document["text"],
    )


@router.get("/chunks")
def list_chunks(
    session_id: SessionDep,
    store: StoreDep,
    doc_type: Optional[DocType] = None,
    section: Optional[str] = None,
):
    """Every chunk the pipeline produced. Powers the 'RAG Inspector' view."""
    chunks = store.list_chunks(session_id, doc_type=doc_type, section=section)
    return {
        "total": len(chunks),
        "chunks": [
            ChunkOut(
                chunk_id=chunk["chunk_id"],
                doc_type=chunk["doc_type"],
                doc_name=chunk["doc_name"],
                section=chunk["section"],
                page=chunk["page"],
                chunk_index=chunk["chunk_index"],
                text=chunk["text"],
                char_start=chunk["char_start"],
                char_end=chunk["char_end"],
            )
            for chunk in chunks
        ],
    }


@router.get("/chunks/{chunk_id}", response_model=ChunkOut)
def get_chunk(session_id: SessionDep, chunk_id: str, store: StoreDep) -> ChunkOut:
    """Resolve a citation back to its exact source text."""
    chunk = store.get_chunk(session_id, chunk_id)
    if not chunk:
        raise SessionNotFound(
            "That source passage no longer exists.",
            hint="Re-run the analysis to refresh the citations.",
            code="chunk_not_found",
        )
    return ChunkOut(
        chunk_id=chunk["chunk_id"],
        doc_type=chunk["doc_type"],
        doc_name=chunk["doc_name"],
        section=chunk["section"],
        page=chunk["page"],
        chunk_index=chunk["chunk_index"],
        text=chunk["text"],
        char_start=chunk["char_start"],
        char_end=chunk["char_end"],
    )


@router.post("/search")
async def semantic_search(
    session_id: SessionDep,
    payload: SearchRequest,
    settings: SettingsDep,
    store: StoreDep,
):
    """Run retrieval on its own, with no LLM.

    This endpoint exists so the retrieval step can be demonstrated in
    isolation: type a query, see the exact chunks and similarity scores that
    would be handed to the LLM.
    """
    retriever = get_retriever(settings)
    results = await run_in_threadpool(
        retriever.retrieve,
        session_id,
        payload.query,
        top_k=payload.top_k,
        doc_type=payload.doc_type,
    )
    for index, chunk in enumerate(results, start=1):
        chunk.ref = f"S{index}"
    return {
        "query": payload.query,
        "embedding_model": retriever.embedder_info,
        "vector_store": retriever.store_info,
        "results": [chunk.to_source() for chunk in results],
    }
