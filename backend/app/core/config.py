"""Application settings.

Everything configurable lives here and is read from environment variables /
`backend/.env`. Nothing secret is ever hard-coded, and nothing secret is ever
sent to the frontend.
"""

from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from typing_extensions import Annotated

# `NoDecode` matters more than it looks. By default pydantic-settings tries to
# JSON-decode any complex field (like List[str]) read from a .env file, and it
# does that *before* field validators run. So a perfectly reasonable line like
#
#     CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
#
# blows up with "error parsing value for field cors_origins" -- it isn't valid
# JSON. NoDecode turns that pre-parsing off and hands the raw string to our own
# validator below, which splits it on commas.
CsvList = Annotated[List[str], NoDecode]

# backend/app/core/config.py -> backend/
BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # -- App ---------------------------------------------------------------
    app_name: str = "Resume + JD RAG Assistant"
    debug: bool = False

    # -- LLM ---------------------------------------------------------------
    # `auto` picks whichever provider has a usable key (Anthropic first).
    llm_provider: str = "auto"  # auto | anthropic | groq

    anthropic_api_key: Optional[str] = None
    llm_model: str = "claude-opus-5"

    groq_api_key: Optional[str] = None
    # gpt-oss-120b is the model on Groq that reliably honours strict JSON
    # schemas, which this whole backend depends on. Smaller models on the
    # platform return schema-shaped but semantically wrong output.
    groq_model: str = "openai/gpt-oss-120b"
    # Groq charges input + *reserved* output against a tokens-per-minute
    # budget, so the output reservation is sized from what's left after the
    # prompt. Raise groq_tpm_budget if you upgrade off the free tier
    # (console.groq.com shows your real limit in the x-ratelimit headers).
    groq_tpm_budget: int = 8000
    groq_max_tokens: int = 5000
    # A rate-limited request is retried after waiting for the bucket to refill,
    # which is what makes the free tier usable at all.
    groq_rate_limit_retries: int = 2

    llm_effort: str = "high"
    llm_extraction_effort: str = "medium"
    llm_max_tokens: int = 8000

    # -- Embeddings --------------------------------------------------------
    embedding_provider: str = "auto"  # auto | local | hash
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # -- Vector store ------------------------------------------------------
    vector_store: str = "auto"  # auto | chroma | numpy

    # -- Chunking / retrieval ---------------------------------------------
    chunk_size: int = 900
    chunk_overlap: int = 150
    retrieval_top_k: int = 8

    # -- Uploads -----------------------------------------------------------
    max_upload_mb: int = 8
    allowed_extensions: CsvList = Field(
        default_factory=lambda: [
            ".pdf", ".docx", ".txt", ".md",
            # Screenshots and phone photos of a posting are read with OCR.
            ".png", ".jpg", ".jpeg", ".webp", ".heic", ".tiff",
        ]
    )

    # -- Privacy -----------------------------------------------------------
    session_ttl_hours: int = 24

    # -- CORS --------------------------------------------------------------
    cors_origins: CsvList = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )

    # -- Paths -------------------------------------------------------------
    data_dir: Path = PROJECT_ROOT / "data"

    @field_validator("cors_origins", "allowed_extensions", mode="before")
    @classmethod
    def _split_csv(cls, value):
        """Allow `A,B,C` in .env as well as a real JSON list."""
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    # -- Derived paths -----------------------------------------------------
    @property
    def storage_dir(self) -> Path:
        return self.data_dir / "storage"

    @property
    def db_path(self) -> Path:
        return self.storage_dir / "app.db"

    @property
    def chroma_dir(self) -> Path:
        return self.storage_dir / "chroma"

    @property
    def vectors_dir(self) -> Path:
        return self.storage_dir / "vectors"

    @property
    def documents_dir(self) -> Path:
        """Sample resume / job descriptions shipped with the project."""
        return self.data_dir / "documents"

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    def ensure_dirs(self) -> None:
        for path in (self.storage_dir, self.chroma_dir, self.vectors_dir, self.documents_dir):
            path.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton (imported everywhere instead of re-reading env)."""
    settings = Settings()
    settings.ensure_dirs()
    return settings
