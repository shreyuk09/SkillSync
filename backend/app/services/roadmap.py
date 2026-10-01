"""Personalised learning roadmap.

Built only from the gaps the match analysis actually found. The number of weeks
scales with the number of high-priority gaps, so someone missing one skill
doesn't get a 12-week plan.
"""

from typing import Any, Dict, List

from app.core.config import Settings
from app.core.logging import get_logger
from app.models.store import Store
from app.rag.generation import generate_grounded
from app.rag.llm import get_llm
from app.rag.prompts import ROADMAP_SCHEMA, ROADMAP_SYSTEM, json_block
from app.rag.retriever import get_retriever
from app.services.jd_analyzer import get_jd_profile
from app.services.match_scorer import compute_match
from app.services.resume_analyzer import all_resume_skills, get_resume_profile

logger = get_logger(__name__)

ANALYSIS_KIND = "roadmap"


def _suggest_duration(high_priority: int, medium_priority: int) -> int:
    """Roughly one to two weeks per gap, clamped to something achievable."""
    weeks = high_priority * 2 + medium_priority
    return max(2, min(12, weeks))


def generate_roadmap(
    session_id: str,
    settings: Settings,
    store: Store,
    *,
    refresh: bool = False,
    weeks: int = 0,
) -> Dict[str, Any]:
    cache_key = ANALYSIS_KIND if not weeks else f"{ANALYSIS_KIND}:{weeks}"
    if not refresh:
        cached = store.get_analysis(session_id, cache_key)
        if cached:
            return cached

    match = compute_match(session_id, settings, store)
    jd_profile = get_jd_profile(session_id, settings, store)
    resume_profile = get_resume_profile(session_id, settings, store)
    retriever = get_retriever(settings)
    llm = get_llm(settings)

    missing = match["skills"]["missing"]
    partial = match["skills"]["partial"]

    required_missing = [item for item in missing if item["importance"] == "required"]
    preferred_missing = [item for item in missing if item["importance"] == "preferred"]

    if not missing and not partial:
        payload = {
            "target_role": jd_profile.get("job_title", ""),
            "summary": (
                "Your resume already covers every skill this job description asks for. "
                "There is no skill gap to close, so the best use of your time is "
                "deepening the skills you have and preparing for the interview."
            ),
            "duration_weeks": 0,
            "skills": [],
            "weeks": [],
            "after_roadmap": [],
            "sources": [],
            "no_gaps": True,
        }
        store.save_analysis(session_id, cache_key, payload)
        return payload

    duration = weeks or _suggest_duration(len(required_missing), len(preferred_missing) + len(partial))

    query = " ".join(
        [jd_profile.get("job_title", "")]
        + [item["skill"] for item in missing[:8]]
        + [item["skill"] for item in partial[:5]]
    )
    chunks = retriever.retrieve_pair(
        session_id, query, resume_k=5, jd_k=5
    )

    context = {
        "target_role": jd_profile.get("job_title", ""),
        "seniority": jd_profile.get("seniority", ""),
        "weeks_available": duration,
        "missing_required_skills": [
            {"skill": item["skill"], "why_it_matters": item["reason"]}
            for item in required_missing
        ],
        "missing_preferred_skills": [item["skill"] for item in preferred_missing],
        "weak_skills_needing_evidence": [
            {"skill": item["skill"], "why_weak": item["reason"]} for item in partial
        ],
        "skills_they_already_have": all_resume_skills(resume_profile)[:30],
        "their_projects": [
            p.get("name") for p in (resume_profile.get("projects") or [])
        ],
        "overall_match_now": match["overall"],
    }

    task = (
        f"Build a {duration}-week learning roadmap that closes these specific gaps. "
        "Use exactly {duration} entries in `weeks`, numbered 1 upward. "
        "Build every practice project on top of the skills and projects they already have."
    ).replace("{duration}", str(duration))

    result = generate_grounded(
        llm,
        system=ROADMAP_SYSTEM,
        task=task,
        chunks=chunks,
        schema=ROADMAP_SCHEMA,
        effort=settings.llm_effort,
        extra_context=json_block("SKILL GAPS FOUND BY THE ANALYSIS", context),
    )

    # Trust our own gap list over the model's: never plan for a skill the
    # analysis didn't actually flag.
    flagged = {item["skill"].lower() for item in missing + partial}
    planned_skills: List[Dict[str, Any]] = [
        skill
        for skill in (result.data.get("skills") or [])
        if str(skill.get("skill", "")).lower() in flagged
    ]

    payload = {
        "target_role": result.data.get("target_role") or jd_profile.get("job_title", ""),
        "summary": result.data.get("summary", ""),
        "duration_weeks": result.data.get("duration_weeks") or duration,
        "skills": planned_skills,
        "weeks": result.data.get("weeks") or [],
        "after_roadmap": result.data.get("after_roadmap") or [],
        "sources": result.sources,
        "no_gaps": False,
        "gap_counts": {
            "required_missing": len(required_missing),
            "preferred_missing": len(preferred_missing),
            "partial": len(partial),
        },
    }

    store.save_analysis(session_id, cache_key, payload)
    return payload
