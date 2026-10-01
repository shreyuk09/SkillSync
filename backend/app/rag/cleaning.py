"""STAGE 2 -- Text cleaning.

PDF extraction produces artefacts that hurt both embeddings and the LLM:
ligatures, bullet glyphs, hyphens left over from line wrapping, page headers
repeated on every page, and lines broken mid-sentence.

Cleaning happens *before* chunking so that every downstream stage sees tidy
text. We are careful never to delete content -- only to normalise it.
"""

import re
from collections import Counter
from typing import List, Set

from app.rag.extraction import ExtractedDocument, Page
from app.utils.text import normalize_whitespace

# Unicode oddities that PDF extractors love to emit.
_REPLACEMENTS = {
    "‘": "'", "’": "'", "“": '"', "”": '"',
    "–": "-", "—": " - ", "−": "-",
    "ﬁ": "fi", "ﬂ": "fl", " ": " ", "​": "",
    "": "* ", "•": "* ", "●": "* ", "▪": "* ",
    "■": "* ", "‣": "* ", "⁃": "* ", "­": "",
}

_HYPHEN_LINEBREAK = re.compile(r"(\w)-\n(\w)")
_MULTI_DOT_LEADER = re.compile(r"\.{4,}")
_EMAIL_SPACING = re.compile(r"\s*@\s*")
_URL_SPACING = re.compile(r"(https?)\s*:\s*//\s*")
_TRAILING_PAGE_NUM = re.compile(r"^\s*(page\s*)?\d+\s*(of\s*\d+)?\s*$", re.IGNORECASE)


def find_boilerplate(pages: List[Page], min_repeats: int = 3) -> Set[str]:
    """Find short lines that repeat across many pages.

    A line that shows up on 3+ pages and is short is almost certainly a running
    header ("John Doe -- Resume") or a footer, not real content.
    """
    counter: Counter = Counter()
    for page in pages:
        # Count each distinct line once per page, so a word repeated inside one
        # page doesn't look like a header.
        seen = {line.strip() for line in page.text.split("\n") if 3 < len(line.strip()) <= 60}
        counter.update(seen)
    return {line for line, count in counter.items() if count >= min_repeats}


def _strip_lines(text: str, boilerplate: Set[str]) -> str:
    if not boilerplate:
        return text
    return "\n".join(line for line in text.split("\n") if line.strip() not in boilerplate)


def _join_wrapped_lines(text: str) -> str:
    """Re-join sentences that a PDF split across two lines.

    A line is treated as wrapped when it doesn't end in punctuation and the
    next line starts lower-case -- a strong signal it's the same sentence.
    """
    lines = text.split("\n")
    out: List[str] = []

    for line in lines:
        stripped = line.rstrip()
        if (
            out
            and stripped
            and out[-1]
            and not out[-1].endswith((".", ":", ";", "!", "?", ",", "-"))
            and stripped[:1].islower()
            and not stripped.startswith("*")
            and len(out[-1]) > 40
        ):
            out[-1] = out[-1] + " " + stripped.lstrip()
        else:
            out.append(stripped)

    return "\n".join(out)


def clean_text(text: str, boilerplate: Set[str] = frozenset()) -> str:
    """Normalise extracted document text. Content-preserving."""
    if not text:
        return ""

    for bad, good in _REPLACEMENTS.items():
        text = text.replace(bad, good)

    # "micro-\nservices" -> "microservices"
    text = _HYPHEN_LINEBREAK.sub(r"\1\2", text)
    text = _MULTI_DOT_LEADER.sub(" ", text)
    text = _EMAIL_SPACING.sub("@", text)
    text = _URL_SPACING.sub(r"\1://", text)

    text = _strip_lines(text, boilerplate)

    # Drop bare page numbers sitting on their own line.
    text = "\n".join(
        line for line in text.split("\n") if not _TRAILING_PAGE_NUM.match(line)
    )

    text = _join_wrapped_lines(text)
    return normalize_whitespace(text)


def clean_document(document: ExtractedDocument) -> ExtractedDocument:
    """Clean every page and rebuild the document text *and* its page map.

    Cleaning changes the length of the text, which would invalidate the
    character offsets recorded during extraction. So instead of cleaning the
    joined text, we clean page by page and recompute the offsets -- that keeps
    "which page did this chunk come from?" correct all the way to the UI.
    """
    boilerplate = find_boilerplate(document.pages)

    rebuilt: List[Page] = []
    buffer: List[str] = []
    cursor = 0

    for page in document.pages:
        cleaned = clean_text(page.text, boilerplate)
        if not cleaned:
            continue
        block = cleaned + "\n\n"
        rebuilt.append(
            Page(
                number=page.number,
                text=cleaned,
                char_start=cursor,
                char_end=cursor + len(block),
            )
        )
        buffer.append(block)
        cursor += len(block)

    full_text = "".join(buffer).strip()

    return ExtractedDocument(
        text=full_text,
        pages=rebuilt,
        page_count=len(rebuilt),
        source_format=document.source_format,
        pages_are_synthetic=document.pages_are_synthetic,
    )
