"""Health + capability reporting.

The frontend calls this on boot so it can tell the user exactly which
embedding model and vector store are active, and warn if no API key is set --
instead of failing mysteriously on the first upload.
"""

from fastapi import APIRouter

from app import __version__
from app.api.deps import SettingsDep
from app.rag.embeddings import get_embedder
from app.rag.llm import active_model, detect_provider, is_configured
from app.rag.vector_store import get_vector_store
from app.schemas.common import HealthResponse, RagStatus

router = APIRouter(tags=["system"])

PROVIDER_LABEL = {"groq": "Groq", "anthropic": "Anthropic"}


@router.get("/health", response_model=HealthResponse)
def health(settings: SettingsDep) -> HealthResponse:
    warnings = []

    embedder = get_embedder(settings)
    store = get_vector_store(settings)
    provider = detect_provider(settings)
    llm_ready = is_configured(settings)

    if not llm_ready:
        warnings.append(
            "No LLM API key is configured. Documents can still be uploaded, "
            "chunked, embedded and searched, but analysis and chat need a key. "
            "Set GROQ_API_KEY (free tier) or ANTHROPIC_API_KEY in backend/.env."
        )
    if not embedder.is_semantic:
        warnings.append(
            "Running the built-in hashing embedder. Install sentence-transformers "
            "for true semantic retrieval."
        )

    return HealthResponse(
        status="ok",
        version=__version__,
        rag=RagStatus(
            embedding_provider=embedder.name,
            embedding_model=embedder.display_name,
            embedding_dimension=embedder.dimension,
            semantic_embeddings=embedder.is_semantic,
            vector_store=store.display_name,
            llm_provider=PROVIDER_LABEL.get(provider or "", "Not configured"),
            llm_model=active_model(settings),
            llm_configured=llm_ready,
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
            retrieval_top_k=settings.retrieval_top_k,
        ),
        warnings=warnings,
    )
