"""STAGE 10 -- Grounded generation + source citation.

This module is the join between the two halves of RAG:

    retriever  ->  prompts  ->  llm  ->  [here]  ->  answer + real sources

Its one job beyond calling the model is **resolving citations**. The model
writes "[S2]"; this module maps S2 back to the exact chunk it came from, so the
UI can render a clickable card showing the real extracted text, its section and
its page. A citation the model invented (an [S9] that was never in the context)
is dropped rather than shown -- a fake source is worse than no source.
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from app.core.config import Settings
from app.core.logging import get_logger
from app.rag.llm import BaseLLM
from app.rag.prompts import build_context_block, refs_index
from app.rag.retriever import RetrievedChunk

logger = get_logger(__name__)

_REF_PATTERN = re.compile(r"\[(S\d+)\]")


@dataclass
class GroundedResult:
    """A model response plus the passages that actually backed it."""

    data: Dict[str, Any]
    sources: List[Dict[str, Any]] = field(default_factory=list)
    retrieved: List[RetrievedChunk] = field(default_factory=list)

    @property
    def retrieval_trace(self) -> List[Dict[str, Any]]:
        """What retrieval returned, shown in the UI's "how this was answered"."""
        return [
            {
                "ref": chunk.ref,
                "citation": chunk.citation,
                "score": round(chunk.score, 3),
                "chunk_id": chunk.chunk_id,
            }
            for chunk in self.retrieved
        ]


def collect_cited_refs(payload: Any) -> List[str]:
    """Find every [S#] mentioned anywhere inside a model response."""
    found: List[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, str):
            found.extend(_REF_PATTERN.findall(node))
        elif isinstance(node, dict):
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(payload)
    # Preserve order, drop duplicates.
    seen = set()
    ordered = []
    for ref in found:
        if ref not in seen:
            seen.add(ref)
            ordered.append(ref)
    return ordered


def resolve_sources(
    payload: Any,
    chunks: Sequence[RetrievedChunk],
    *,
    explicit_refs: Optional[Sequence[str]] = None,
    include_all_on_empty: bool = False,
) -> List[Dict[str, Any]]:
    """Turn the refs a model used into real, verifiable source cards."""
    index = refs_index(chunks)

    wanted: List[str] = []
    for ref in list(explicit_refs or []) + collect_cited_refs(payload):
        normalized = str(ref).strip().strip("[]").upper()
        if normalized in index and normalized not in wanted:
            wanted.append(normalized)

    if not wanted and include_all_on_empty:
        wanted = [chunk.ref for chunk in chunks if chunk.ref]

    return [index[ref].to_source() for ref in wanted]


def strip_ref_markers(text: str) -> str:
    """Remove [S#] markers, used when a string is shown without source cards."""
    return _REF_PATTERN.sub("", text).replace("  ", " ").strip()


def generate_grounded(
    llm: BaseLLM,
    *,
    system: str,
    task: str,
    chunks: Sequence[RetrievedChunk],
    schema: Dict[str, Any],
    max_tokens: Optional[int] = None,
    effort: Optional[str] = None,
    extra_context: str = "",
    explicit_refs_key: Optional[str] = None,
    include_all_sources: bool = False,
) -> GroundedResult:
    """Run one grounded, schema-validated generation.

    `task` is the instruction; `chunks` are the retrieved passages that become
    the CONTEXT block. Anything in `extra_context` (already-computed scores,
    parsed profiles) is added as clearly-labelled derived data.
    """
    context_block = build_context_block(chunks)

    user_parts = [context_block]
    if extra_context:
        user_parts.append(extra_context)
    user_parts.append(task)
    user = "\n\n".join(part for part in user_parts if part.strip())

    data = llm.complete_json(
        system=system, user=user, schema=schema, max_tokens=max_tokens, effort=effort
    )

    explicit = data.get(explicit_refs_key) if explicit_refs_key else None
    sources = resolve_sources(
        data,
        chunks,
        explicit_refs=explicit if isinstance(explicit, list) else None,
        include_all_on_empty=include_all_sources,
    )

    return GroundedResult(data=data, sources=sources, retrieved=list(chunks))


def format_history(messages: Sequence[Dict[str, Any]], limit: int = 6) -> str:
    """Render recent chat turns so follow-up questions keep their referent.

    Only the text is carried forward -- the previous turn's sources are not
    re-injected as facts, so every answer is grounded in a fresh retrieval.
    """
    recent = [m for m in messages if m.get("role") in ("user", "assistant")][-limit:]
    if not recent:
        return ""
    lines = ["RECENT CONVERSATION (for pronouns and follow-ups only -- not a source of facts):"]
    for message in recent:
        speaker = "User" if message["role"] == "user" else "Assistant"
        content = str(message.get("content", ""))
        if len(content) > 400:
            content = content[:400] + "..."
        lines.append(f"{speaker}: {content}")
    return "\n".join(lines)
