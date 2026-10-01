"""Typed application errors.

Every error the user can trigger gets a stable `code`, a human-readable
`message`, and an optional `hint` telling them what to do next. The API never
leaks a Python stack trace to the browser.
"""

from typing import Optional


class AppError(Exception):
    """Base class for all expected, user-facing failures."""

    code = "internal_error"
    status_code = 500
    message = "Something went wrong on our side."
    hint: Optional[str] = None

    def __init__(
        self,
        message: Optional[str] = None,
        *,
        hint: Optional[str] = None,
        code: Optional[str] = None,
        status_code: Optional[int] = None,
    ) -> None:
        self.message = message or self.message
        self.hint = hint if hint is not None else self.hint
        self.code = code or self.code
        self.status_code = status_code or self.status_code
        super().__init__(self.message)

    def to_dict(self) -> dict:
        return {"code": self.code, "message": self.message, "hint": self.hint}


# --------------------------------------------------------------------------
# Upload / document errors
# --------------------------------------------------------------------------
class UnsupportedFileType(AppError):
    code = "unsupported_file_type"
    status_code = 415
    message = "That file type isn't supported."
    hint = "Upload a PDF, DOCX, TXT or MD file."


class FileTooLarge(AppError):
    code = "file_too_large"
    status_code = 413
    message = "That file is too large."
    hint = "Try a file under the size limit, or paste the text instead."


class EmptyDocument(AppError):
    code = "empty_document"
    status_code = 422
    message = "We couldn't find any readable text in that document."
    hint = (
        "If it's a scanned PDF, the text is stored as an image and can't be read. "
        "Export a text-based PDF or paste the content directly."
    )


class ExtractionError(AppError):
    code = "extraction_failed"
    status_code = 422
    message = "We couldn't read that file -- it may be corrupted or password protected."
    hint = "Try re-exporting the document, or paste the text instead."


# --------------------------------------------------------------------------
# RAG pipeline errors
# --------------------------------------------------------------------------
class EmbeddingError(AppError):
    code = "embedding_failed"
    status_code = 503
    message = "The embedding model failed while indexing your document."
    hint = "Check the backend logs, then try uploading again."


class VectorStoreError(AppError):
    code = "vector_store_failed"
    status_code = 503
    message = "The vector database is unavailable."
    hint = "Restart the backend. If it persists, delete data/storage/ and re-upload."


class LLMError(AppError):
    code = "llm_failed"
    status_code = 503
    message = "The AI model is temporarily unavailable."
    hint = "Wait a few seconds and try again."


class LLMNotConfigured(AppError):
    code = "llm_not_configured"
    status_code = 503
    message = "No Anthropic API key is configured on the server."
    hint = "Add ANTHROPIC_API_KEY to backend/.env and restart the backend."


# --------------------------------------------------------------------------
# Workflow errors
# --------------------------------------------------------------------------
class SessionNotFound(AppError):
    code = "session_not_found"
    status_code = 404
    message = "That session has expired or doesn't exist."
    hint = "Start a new analysis from the home page."


class ResumeMissing(AppError):
    code = "resume_missing"
    status_code = 409
    message = "No resume has been uploaded yet."
    hint = "Upload your resume first."


class JobDescriptionMissing(AppError):
    code = "jd_missing"
    status_code = 409
    message = "No job description has been added yet."
    hint = "Upload or paste a job description first."
