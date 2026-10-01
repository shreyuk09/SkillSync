"""Job description analysis -- structured requirements out of JD text."""

from typing import Any, Dict, List, Optional

from app.core.config import Settings
from app.core.errors import JobDescriptionMissing
from app.core.logging import get_logger
from app.models.store import Store
from app.rag.llm import get_llm
from app.rag.prompts import JD_PARSE_SYSTEM, JD_SCHEMA, build_document_block

logger = get_logger(__name__)

ANALYSIS_KIND = "jd_profile"


def get_jd_profile(
    session_id: str, settings: Settings, store: Store, *, refresh: bool = False
) -> Dict[str, Any]:
    """Parse the session's job description, using the cache unless `refresh`."""
    if not refresh:
        cached = store.get_analysis(session_id, ANALYSIS_KIND)
        if cached:
            return cached

    document = store.get_document(session_id, "jd")
    if not document:
        raise JobDescriptionMissing()

    llm = get_llm(settings)
    task = (
        "Extract every field in the schema from the job description below. "
        "Only include requirements the posting actually states."
    )
    user = build_document_block("JOB DESCRIPTION", document["text"]) + "\n\n" + task

    logger.info("Parsing job description for session %s", session_id)
    profile = llm.complete_json(
        system=JD_PARSE_SYSTEM,
        user=user,
        schema=JD_SCHEMA,
        effort=settings.llm_extraction_effort,
    )

    profile["stats"] = {
        "required_skill_count": len(profile.get("required_skills") or []),
        "preferred_skill_count": len(profile.get("preferred_skills") or []),
        "responsibility_count": len(profile.get("responsibilities") or []),
        "keyword_count": len(profile.get("keywords") or []),
        "word_count": len((document.get("text") or "").split()),
        "sections_found": document.get("sections") or [],
    }
    profile["document"] = {
        "name": document["name"],
        "format": document["source_format"],
        "pages": document["page_count"],
        "chunks": document["chunk_count"],
        "sections": document["sections"],
    }

    store.save_analysis(session_id, ANALYSIS_KIND, profile)
    return profile


def all_jd_skills(profile: Dict[str, Any]) -> List[str]:
    skills = list(profile.get("required_skills") or [])
    skills += list(profile.get("preferred_skills") or [])
    skills += list(profile.get("tools_and_technologies") or [])
    seen = set()
    unique = []
    for skill in skills:
        key = str(skill).strip().lower()
        if key and key not in seen:
            seen.add(key)
            unique.append(str(skill).strip())
    return unique
