"""Resume improvement suggestions.

Suggestions are generated from retrieved resume chunks so the `original` text
is real, quotable and verifiable. Every suggestion is checked against the
resume before it is returned: if the model's "original" doesn't actually appear
in the document, the suggestion is dropped rather than shown. That check is the
difference between a rewrite and a fabrication.

Accept/reject decisions are stored per session so the UI keeps its state.
"""

import difflib
import re
from typing import Any, Dict, List

from app.core.config import Settings
from app.core.logging import get_logger
from app.models.store import Store
from app.rag.generation import generate_grounded
from app.rag.llm import get_llm
from app.rag.prompts import IMPROVEMENTS_SCHEMA, IMPROVEMENTS_SYSTEM, json_block
from app.rag.retriever import get_retriever
from app.services.jd_analyzer import get_jd_profile
from app.services.match_scorer import compute_match

logger = get_logger(__name__)

ANALYSIS_KIND = "improvements"
DECISIONS_KIND = "improvement_decisions"

# How close the model's quoted "original" must be to real resume text.
QUOTE_SIMILARITY_FLOOR = 0.72


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _verify_original(original: str, resume_text: str) -> bool:
    """Is this quote genuinely in the resume?

    Exact substring first; then a fuzzy check, because the model may normalise
    a bullet glyph or a stray double space.
    """
    if not original.strip():
        return False

    haystack = _normalize(resume_text)
    needle = _normalize(original)

    if needle in haystack:
        return True

    # Fuzzy: compare against each line of similar length.
    for line in resume_text.split("\n"):
        candidate = _normalize(line)
        if not candidate or abs(len(candidate) - len(needle)) > max(40, len(needle) * 0.5):
            continue
        if difflib.SequenceMatcher(None, candidate, needle).ratio() >= QUOTE_SIMILARITY_FLOOR:
            return True
    return False


def generate_improvements(
    session_id: str, settings: Settings, store: Store, *, refresh: bool = False
) -> Dict[str, Any]:
    if not refresh:
        cached = store.get_analysis(session_id, ANALYSIS_KIND)
        if cached:
            return _with_decisions(cached, session_id, store)

    match = compute_match(session_id, settings, store)
    jd_profile = get_jd_profile(session_id, settings, store)
    retriever = get_retriever(settings)
    llm = get_llm(settings)

    resume_document = store.get_document(session_id, "resume") or {}
    resume_text = resume_document.get("text", "")

    # Retrieve the parts of the resume most worth rewriting for this job, plus
    # the JD language we're allowed to borrow.
    query = " ".join(
        [jd_profile.get("job_title", "")]
        + (jd_profile.get("required_skills") or [])[:8]
        + (jd_profile.get("responsibilities") or [])[:4]
    )
    chunks = retriever.retrieve_pair(
        session_id, query, resume_k=8, jd_k=4
    )

    context = {
        "job_title": jd_profile.get("job_title", ""),
        "required_skills": jd_profile.get("required_skills") or [],
        "job_keywords": (jd_profile.get("keywords") or [])[:15],
        "skills_you_have_but_undersell": [
            item["skill"] for item in match["skills"]["partial"]
        ],
        "skills_you_are_missing": [item["skill"] for item in match["skills"]["missing"]],
        "your_strongest_projects": [
            {"name": item["name"], "relevance": item["relevance"]}
            for item in (match.get("projects") or [])[:3]
        ],
    }

    count = "4 to 5" if llm.compact_output else "5 to 8"
    task = (
        f"Write {count} specific rewrite suggestions for this resume, targeting this "
        "job. Quote each `original` exactly as it appears in the CONTEXT passages. "
        "`impact` must be exactly one of: high, medium, low."
    )

    result = generate_grounded(
        llm,
        system=IMPROVEMENTS_SYSTEM,
        task=task,
        chunks=chunks,
        schema=IMPROVEMENTS_SCHEMA,
        effort=settings.llm_effort,
        extra_context=json_block("MATCH ANALYSIS CONTEXT", context),
    )

    verified: List[Dict[str, Any]] = []
    rejected = 0
    for index, suggestion in enumerate(result.data.get("suggestions") or []):
        original = str(suggestion.get("original", ""))
        if not _verify_original(original, resume_text):
            rejected += 1
            logger.info("Dropped a suggestion whose quote isn't in the resume: %r", original[:80])
            continue
        suggestion["id"] = suggestion.get("id") or f"imp-{index + 1}"
        suggestion["verified"] = True
        # The card always shows a plain-English headline and consequence. Fall
        # back to the older fields so a result cached before these existed
        # still renders a complete card instead of an empty one.
        section = str(suggestion.get("section") or "your resume").strip()
        if not str(suggestion.get("what_to_fix") or "").strip():
            suggestion["what_to_fix"] = f"Reword this line in your {section} section."
        if not str(suggestion.get("why_it_matters") or "").strip():
            suggestion["why_it_matters"] = (
                str(suggestion.get("reason") or "").strip()
                or "A clearer line makes your fit for this job easier to see."
            )
        verified.append(suggestion)

    payload = {
        "suggestions": verified,
        "formatting_notes": result.data.get("formatting_notes") or [],
        "sources": result.sources,
        "dropped_unverified": rejected,
        "note": (
            "Every suggestion below was checked against your actual resume text. "
            f"{rejected} suggestion(s) were discarded because the quoted original "
            "could not be found in your document."
            if rejected
            else "Every suggestion below quotes text that really appears in your resume."
        ),
    }

    store.save_analysis(session_id, ANALYSIS_KIND, payload)
    return _with_decisions(payload, session_id, store)


# --------------------------------------------------------------------------
# Accept / reject state
# --------------------------------------------------------------------------
def _with_decisions(payload: Dict[str, Any], session_id: str, store: Store) -> Dict[str, Any]:
    decisions = store.get_analysis(session_id, DECISIONS_KIND) or {}
    enriched = dict(payload)
    enriched["suggestions"] = [
        {**suggestion, "decision": decisions.get(suggestion["id"], "pending")}
        for suggestion in payload.get("suggestions", [])
    ]
    enriched["accepted_count"] = sum(
        1 for item in enriched["suggestions"] if item["decision"] == "accepted"
    )
    enriched["rejected_count"] = sum(
        1 for item in enriched["suggestions"] if item["decision"] == "rejected"
    )
    return enriched


def set_decision(
    session_id: str, suggestion_id: str, decision: str, store: Store
) -> Dict[str, str]:
    decisions = store.get_analysis(session_id, DECISIONS_KIND) or {}
    if decision == "pending":
        decisions.pop(suggestion_id, None)
    else:
        decisions[suggestion_id] = decision
    store.save_analysis(session_id, DECISIONS_KIND, decisions)
    return decisions
