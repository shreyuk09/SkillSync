"""Resume analysis -- turn the stored resume text into a structured profile.

Note on why parsing reads the *whole* document instead of retrieved chunks:
extraction needs completeness (every project, every certification), while
retrieval optimises for relevance. Retrieval is used for every question the
user asks afterwards; parsing is a one-time full read.

The result is cached in SQLite so the LLM is called once per uploaded resume,
not once per page view.
"""

from typing import Any, Dict, List, Optional

from app.core.config import Settings
from app.core.errors import ResumeMissing
from app.core.logging import get_logger
from app.models.store import Store
from app.rag.llm import get_llm
from app.rag.prompts import RESUME_PARSE_SYSTEM, RESUME_SCHEMA, build_document_block

logger = get_logger(__name__)

ANALYSIS_KIND = "resume_profile"


def _derive_stats(profile: Dict[str, Any], document: Dict[str, Any]) -> Dict[str, Any]:
    """Counts the UI shows as badges. Computed, never asked of the model."""
    return {
        "technical_skill_count": len(profile.get("technical_skills") or []),
        "soft_skill_count": len(profile.get("soft_skills") or []),
        "project_count": len(profile.get("projects") or []),
        "experience_count": len(profile.get("experience") or []),
        "internship_count": len(profile.get("internships") or []),
        "certification_count": len(profile.get("certifications") or []),
        "achievement_count": len(profile.get("achievements") or []),
        "publication_count": len(profile.get("publications") or []),
        "education_count": len(profile.get("education") or []),
        "page_count": document.get("page_count", 0),
        "word_count": len((document.get("text") or "").split()),
        "sections_found": document.get("sections") or [],
    }


def _completeness(profile: Dict[str, Any]) -> Dict[str, Any]:
    """Which standard resume fields are present? Used for the 'strength' card."""
    checks = [
        ("Name", bool(profile.get("name"))),
        ("Email", bool(profile.get("email"))),
        ("Phone", bool(profile.get("phone"))),
        ("Summary / objective", bool(profile.get("summary"))),
        ("Education", bool(profile.get("education"))),
        ("Technical skills", bool(profile.get("technical_skills"))),
        ("Projects", bool(profile.get("projects"))),
        ("Experience or internships",
         bool(profile.get("experience") or profile.get("internships"))),
        ("Certifications", bool(profile.get("certifications"))),
        ("Achievements", bool(profile.get("achievements"))),
    ]
    present = [label for label, ok in checks if ok]
    missing = [label for label, ok in checks if not ok]
    return {
        "present": present,
        "missing": missing,
        "score": round(100 * len(present) / len(checks)),
    }


def get_resume_profile(
    session_id: str, settings: Settings, store: Store, *, refresh: bool = False
) -> Dict[str, Any]:
    """Return the parsed resume profile, using the cache unless `refresh`."""
    if not refresh:
        cached = store.get_analysis(session_id, ANALYSIS_KIND)
        if cached:
            return cached

    document = store.get_document(session_id, "resume")
    if not document:
        raise ResumeMissing()

    llm = get_llm(settings)
    task = (
        "Extract every field in the schema from the resume below. "
        "Leave a field empty when the resume does not contain it."
    )
    user = build_document_block("RESUME", document["text"]) + "\n\n" + task

    logger.info("Parsing resume for session %s", session_id)
    profile = llm.complete_json(
        system=RESUME_PARSE_SYSTEM,
        user=user,
        schema=RESUME_SCHEMA,
        effort=settings.llm_extraction_effort,
    )

    profile["stats"] = _derive_stats(profile, document)
    profile["completeness"] = _completeness(profile)
    profile["document"] = {
        "name": document["name"],
        "format": document["source_format"],
        "pages": document["page_count"],
        "chunks": document["chunk_count"],
        "sections": document["sections"],
    }

    store.save_analysis(session_id, ANALYSIS_KIND, profile)
    return profile


def all_resume_skills(profile: Dict[str, Any]) -> List[str]:
    """Every skill the resume claims, including ones named inside projects."""
    skills: List[str] = list(profile.get("technical_skills") or [])
    for project in profile.get("projects") or []:
        skills.extend(project.get("technologies") or [])
    for role in (profile.get("experience") or []) + (profile.get("internships") or []):
        skills.extend(role.get("technologies") or [])
    seen = set()
    unique = []
    for skill in skills:
        key = str(skill).strip().lower()
        if key and key not in seen:
            seen.add(key)
            unique.append(str(skill).strip())
    return unique
