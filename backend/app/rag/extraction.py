"""STAGE 1 -- Document extraction.

Turns an uploaded file into plain text plus a *page map*, so that later on we
can tell the user exactly where a piece of evidence came from
("Resume -> Projects -> Page 1").

DOCX and TXT files have no real pages, so we synthesise them: every
`CHARS_PER_SYNTHETIC_PAGE` characters counts as one page. That keeps citations
consistent across every file format.
"""

import io
from dataclasses import dataclass, field
from typing import List, Optional

from app.core.errors import EmptyDocument, ExtractionError
from app.core.logging import get_logger
from app.utils.text import normalize_whitespace

logger = get_logger(__name__)

CHARS_PER_SYNTHETIC_PAGE = 3000
MIN_USEFUL_CHARS = 60


@dataclass
class Page:
    number: int  # 1-indexed
    text: str
    char_start: int  # offset of this page inside the full document text
    char_end: int


@dataclass
class ExtractedDocument:
    text: str
    pages: List[Page] = field(default_factory=list)
    page_count: int = 0
    source_format: str = "txt"
    pages_are_synthetic: bool = False

    def page_for_offset(self, offset: int) -> int:
        """Which page does this character offset fall on?"""
        for page in self.pages:
            if page.char_start <= offset < page.char_end:
                return page.number
        return self.pages[-1].number if self.pages else 1


# --------------------------------------------------------------------------
# Format-specific readers
# --------------------------------------------------------------------------
def _extract_pdf(content: bytes) -> List[str]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - dependency is in requirements
        raise ExtractionError(
            "PDF support isn't installed on the server.",
            hint="Run `pip install pypdf` in the backend environment.",
        ) from exc

    try:
        reader = PdfReader(io.BytesIO(content))
        if getattr(reader, "is_encrypted", False):
            # Some PDFs are encrypted with an empty owner password; try that.
            try:
                reader.decrypt("")
            except Exception as exc:
                raise ExtractionError(
                    "That PDF is password protected.",
                    hint="Remove the password, or paste the text instead.",
                ) from exc
        return [(page.extract_text() or "") for page in reader.pages]
    except ExtractionError:
        raise
    except Exception as exc:
        logger.warning("PDF extraction failed: %s", exc)
        raise ExtractionError(
            "We couldn't read that PDF -- it may be corrupted.",
            hint="Try re-exporting it from your editor, or paste the text instead.",
        ) from exc


def _extract_docx(content: bytes) -> List[str]:
    try:
        import docx  # python-docx
    except ImportError as exc:  # pragma: no cover
        raise ExtractionError(
            "DOCX support isn't installed on the server.",
            hint="Run `pip install python-docx` in the backend environment.",
        ) from exc

    try:
        document = docx.Document(io.BytesIO(content))
        parts: List[str] = [p.text for p in document.paragraphs]
        # Resumes often keep skills / education inside tables.
        for table in document.tables:
            for row in table.rows:
                cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                if cells:
                    parts.append(" | ".join(cells))
        return ["\n".join(parts)]
    except Exception as exc:
        logger.warning("DOCX extraction failed: %s", exc)
        raise ExtractionError(
            "We couldn't read that DOCX file -- it may be corrupted.",
            hint="Try re-saving it from Word/Google Docs, or paste the text instead.",
        ) from exc


def _extract_text(content: bytes) -> List[str]:
    for encoding in ("utf-8", "utf-16", "latin-1"):
        try:
            return [content.decode(encoding)]
        except (UnicodeDecodeError, UnicodeError):
            continue
    raise ExtractionError(
        "We couldn't decode that text file.",
        hint="Save it as UTF-8 and try again.",
    )


# --------------------------------------------------------------------------
# Page map construction
# --------------------------------------------------------------------------
def _build_real_pages(page_texts: List[str]) -> "tuple[str, List[Page]]":
    pages: List[Page] = []
    buffer: List[str] = []
    cursor = 0
    number = 0

    for raw in page_texts:
        cleaned = normalize_whitespace(raw)
        if not cleaned:
            # Keep the page number aligned with the real document even when a
            # page yields no text (e.g. a full-page image).
            number += 1
            continue
        number += 1
        block = cleaned + "\n\n"
        pages.append(Page(number=number, text=cleaned, char_start=cursor, char_end=cursor + len(block)))
        buffer.append(block)
        cursor += len(block)

    return "".join(buffer).strip(), pages


def _build_synthetic_pages(text: str) -> List[Page]:
    pages: List[Page] = []
    if not text:
        return pages

    start = 0
    number = 1
    while start < len(text):
        end = min(start + CHARS_PER_SYNTHETIC_PAGE, len(text))
        # Don't cut a paragraph in half if we can avoid it.
        if end < len(text):
            newline = text.rfind("\n", start + CHARS_PER_SYNTHETIC_PAGE // 2, end)
            if newline != -1:
                end = newline + 1
        pages.append(Page(number=number, text=text[start:end], char_start=start, char_end=end))
        start = end
        number += 1
    return pages


IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".heic", ".tiff")


def _extract_image(content: bytes, extension: str) -> str:
    """Read the text in a screenshot or photo of a document."""
    from app.rag.ocr import OCRUnavailable, read_image

    try:
        return read_image(content, suffix=extension)
    except OCRUnavailable as exc:
        raise ExtractionError(
            f"That image couldn't be read. {exc}",
        ) from exc


# --------------------------------------------------------------------------
# Public entry point
# --------------------------------------------------------------------------
def extract_document(content: bytes, extension: str) -> ExtractedDocument:
    """Extract text + a page map from raw file bytes."""
    extension = extension.lower()

    if extension == ".pdf":
        page_texts = _extract_pdf(content)
        text, pages = _build_real_pages(page_texts)
        synthetic = False
        source_format = "pdf"
    elif extension == ".docx":
        page_texts = _extract_docx(content)
        text = normalize_whitespace(page_texts[0])
        pages = _build_synthetic_pages(text)
        synthetic = True
        source_format = "docx"
    elif extension in (".txt", ".md"):
        page_texts = _extract_text(content)
        text = normalize_whitespace(page_texts[0])
        pages = _build_synthetic_pages(text)
        synthetic = True
        source_format = extension.lstrip(".")
    elif extension in IMAGE_EXTENSIONS:
        text = normalize_whitespace(_extract_image(content, extension))
        pages = _build_synthetic_pages(text)
        synthetic = True
        source_format = "image"
    else:
        raise ExtractionError(f"Unsupported extension '{extension}'.")

    if len(text.strip()) < MIN_USEFUL_CHARS:
        raise EmptyDocument(
            "We could open that file, but there was almost no readable text in it.",
            hint=(
                "Scanned PDFs and low-resolution screenshots often have too little "
                "readable text. Export a text-based PDF, use a sharper image, or "
                "paste the content directly."
            ),
        )

    return ExtractedDocument(
        text=text,
        pages=pages,
        page_count=len(pages),
        source_format=source_format,
        pages_are_synthetic=synthetic,
    )


def extract_from_plain_text(text: str) -> ExtractedDocument:
    """Same contract as `extract_document`, for text pasted into the UI."""
    cleaned = normalize_whitespace(text)
    if len(cleaned) < MIN_USEFUL_CHARS:
        raise EmptyDocument(
            "That text is too short to analyse.",
            hint="Paste the full job description (at least a few sentences).",
        )
    pages = _build_synthetic_pages(cleaned)
    return ExtractedDocument(
        text=cleaned,
        pages=pages,
        page_count=len(pages),
        source_format="text",
        pages_are_synthetic=True,
    )
