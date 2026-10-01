"""STAGE 4 -- Chunking.

Why chunk at all? Two reasons:

* An embedding is a single fixed-size vector. Squeezing a whole 2-page resume
  into one vector blurs everything together, and retrieval becomes useless.
* We want to cite a *specific* paragraph, not "somewhere in the resume".

Strategy used here -- **section-aware recursive chunking with overlap**:

1. Never cross a section boundary. A chunk is always about one topic.
2. Inside a section, split on paragraph breaks, then sentence breaks, then
   (only if a single sentence is enormous) on words.
3. Greedily pack pieces up to `chunk_size` characters.
4. Carry `chunk_overlap` characters from the previous chunk into the next one,
   so a fact that straddles a boundary still appears whole somewhere.
5. Prefix each chunk with its section, written as a natural sentence. This is
   measurably better than a terse tag: for the query "what projects has the
   candidate built with React?", the Projects chunk scores 0.506 with a
   natural prefix versus 0.424 with a `[RESUME | Projects]` tag -- and the
   competing Skills chunk drops from 0.484 to 0.402. The natural prefix ranks
   the right chunk first; the tag ranks the wrong one first.

Every chunk carries the metadata the UI needs for a citation:
`doc_id, doc_type, doc_name, section, page, chunk_index, char_start/end`.
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.rag.extraction import ExtractedDocument
from app.rag.sectioning import Section

_PARAGRAPH_SPLIT = re.compile(r"\n\s*\n")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z*])")
_BULLET_LINE = re.compile(r"^\s*[*\-•]\s+")

MIN_CHUNK_CHARS = 40


@dataclass
class Chunk:
    """One retrievable unit of text plus everything needed to cite it."""

    chunk_id: str
    text: str  # text as stored/shown to the user
    embed_text: str  # text actually sent to the embedding model
    doc_id: str
    doc_type: str  # "resume" | "jd"
    doc_name: str
    section: str
    page: int
    chunk_index: int
    char_start: int
    char_end: int
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_metadata(self) -> Dict[str, Any]:
        """Flat, primitive-only metadata -- what vector DBs accept."""
        return {
            "chunk_id": self.chunk_id,
            "doc_id": self.doc_id,
            "doc_type": self.doc_type,
            "doc_name": self.doc_name,
            "section": self.section,
            "page": self.page,
            "chunk_index": self.chunk_index,
            "char_start": self.char_start,
            "char_end": self.char_end,
        }

    @property
    def citation(self) -> str:
        """Human-readable source label shown in the UI."""
        label = "Resume" if self.doc_type == "resume" else "Job Description"
        return f"{label} -> {self.section} -> Page {self.page}"


def _split_paragraph(paragraph: str, limit: int) -> List[str]:
    """Break one oversized paragraph into pieces that fit inside `limit`."""
    if len(paragraph) <= limit:
        return [paragraph]

    pieces: List[str] = []
    for sentence in _SENTENCE_SPLIT.split(paragraph):
        if len(sentence) <= limit:
            pieces.append(sentence)
            continue
        # A single sentence longer than the limit (common in dense JD bullets):
        # fall back to packing words.
        words = sentence.split()
        current: List[str] = []
        length = 0
        for word in words:
            if length + len(word) + 1 > limit and current:
                pieces.append(" ".join(current))
                current, length = [], 0
            current.append(word)
            length += len(word) + 1
        if current:
            pieces.append(" ".join(current))
    return [piece for piece in pieces if piece.strip()]


def _units_for_section(section: Section) -> List[str]:
    """Split a section body into the smallest units we will pack into chunks.

    Bullet lists are the backbone of both resumes and JDs, so consecutive
    bullets are kept as individual units rather than glued into one blob.
    """
    units: List[str] = []
    for paragraph in _PARAGRAPH_SPLIT.split(section.text):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        lines = paragraph.split("\n")
        bullet_count = sum(1 for line in lines if _BULLET_LINE.match(line))
        if bullet_count >= 2:
            units.extend(line.strip() for line in lines if line.strip())
        else:
            units.append(paragraph)
    return units


def chunk_document(
    document: ExtractedDocument,
    sections: List[Section],
    *,
    doc_id: str,
    doc_type: str,
    doc_name: str,
    chunk_size: int = 900,
    chunk_overlap: int = 150,
    start_index: int = 0,
) -> List[Chunk]:
    """Turn a sectioned document into overlapping, metadata-rich chunks."""
    chunks: List[Chunk] = []
    index = start_index

    for section in sections:
        units = _units_for_section(section)
        if not units:
            continue

        buffer: List[str] = []
        buffer_len = 0
        # Offset of the current buffer inside the whole document.
        search_cursor = section.char_start

        def flush(pending: List[str], cursor: int) -> Optional[Chunk]:
            nonlocal index
            body = "\n".join(pending).strip()
            if len(body) < MIN_CHUNK_CHARS:
                return None
            char_start = cursor
            char_end = min(cursor + len(body), len(document.text))
            document_label = "resume" if doc_type == "resume" else "job description"
            chunk = Chunk(
                chunk_id=f"{doc_id}-c{index:04d}",
                text=body,
                # The section label is part of what gets embedded, phrased as
                # ordinary language so the sentence encoder can use it.
                embed_text=f"{section.name} section of the {document_label}. {body}",
                doc_id=doc_id,
                doc_type=doc_type,
                doc_name=doc_name,
                section=section.name,
                page=document.page_for_offset(char_start),
                chunk_index=index,
                char_start=char_start,
                char_end=char_end,
            )
            index += 1
            return chunk

        for unit in units:
            unit_len = len(unit) + 1

            if buffer and buffer_len + unit_len > chunk_size:
                chunk = flush(buffer, search_cursor)
                if chunk:
                    chunks.append(chunk)

                # Build the overlap tail: keep whole trailing units until we
                # have ~chunk_overlap characters of context.
                tail: List[str] = []
                tail_len = 0
                for previous in reversed(buffer):
                    if tail_len + len(previous) > chunk_overlap and tail:
                        break
                    tail.insert(0, previous)
                    tail_len += len(previous) + 1

                consumed = sum(len(item) + 1 for item in buffer) - tail_len
                search_cursor = min(search_cursor + max(consumed, 0), section.char_end)
                buffer = list(tail)
                buffer_len = tail_len

            buffer.append(unit)
            buffer_len += unit_len

        if buffer:
            chunk = flush(buffer, search_cursor)
            if chunk:
                chunks.append(chunk)

    # A very small document (a 3-line pasted JD) may produce nothing above.
    if not chunks and document.text.strip():
        chunks.append(
            Chunk(
                chunk_id=f"{doc_id}-c{start_index:04d}",
                text=document.text.strip(),
                embed_text=document.text.strip(),
                doc_id=doc_id,
                doc_type=doc_type,
                doc_name=doc_name,
                section=sections[0].name if sections else "Other",
                page=1,
                chunk_index=start_index,
                char_start=0,
                char_end=len(document.text),
            )
        )

    return chunks
