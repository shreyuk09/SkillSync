"""Interview question generation.

Questions are built from retrieved chunks of both documents, so project and
experience questions reference projects the candidate actually has. Anything
the model returns that names a project not in the resume is filtered out
before it reaches the UI.
"""

from typing import Any, Dict, List, Optional

from app.core.config import Settings
from app.core.logging import get_logger
from app.models.store import Store
from app.rag.generation import generate_grounded
from app.rag.llm import get_llm
from app.rag.prompts import INTERVIEW_SCHEMA, INTERVIEW_SYSTEM, json_block
from app.rag.retriever import get_retriever
from app.services.jd_analyzer import get_jd_profile
from app.services.match_scorer import compute_match
from app.services.resume_analyzer import get_resume_profile

logger = get_logger(__name__)

ANALYSIS_KIND = "interview"

CATEGORY_LABELS = {
    "technical": "Technical",
    "project": "Projects",
    "experience": "Experience",
    "hr": "HR & Behavioural",
    "company": "Company & Role",
}


def generate_interview_prep(
    session_id: str,
    settings: Settings,
    store: Store,
    *,
    refresh: bool = False,
    focus: Optional[str] = None,
) -> Dict[str, Any]:
    cache_key = ANALYSIS_KIND if not focus else f"{ANALYSIS_KIND}:{focus}"
    if not refresh:
        cached = store.get_analysis(session_id, cache_key)
        if cached:
            return cached

    resume_profile = get_resume_profile(session_id, settings, store)
    jd_profile = get_jd_profile(session_id, settings, store)
    match = compute_match(session_id, settings, store)
    retriever = get_retriever(settings)
    llm = get_llm(settings)

    project_names = [
        str(project.get("name", "")).strip()
        for project in (resume_profile.get("projects") or [])
        if str(project.get("name", "")).strip()
    ]

    query_parts = [
        jd_profile.get("job_title", ""),
        " ".join((jd_profile.get("required_skills") or [])[:10]),
        " ".join(project_names[:5]),
        " ".join((jd_profile.get("responsibilities") or [])[:3]),
    ]
    if focus:
        query_parts.insert(0, focus)
    chunks = retriever.retrieve_pair(
        session_id, " ".join(query_parts), resume_k=8, jd_k=6,
    )

    context = {
        "job_title": jd_profile.get("job_title", ""),
        "company": jd_profile.get("company", ""),
        "seniority": jd_profile.get("seniority", ""),
        "required_skills": jd_profile.get("required_skills") or [],
        "preferred_skills": jd_profile.get("preferred_skills") or [],
        "responsibilities": jd_profile.get("responsibilities") or [],
        "candidate_projects": [
            {"name": p.get("name"), "technologies": p.get("technologies") or []}
            for p in (resume_profile.get("projects") or [])
        ],
        "candidate_roles": [
            {"title": r.get("title"), "organization": r.get("organization")}
            for r in (resume_profile.get("experience") or [])
            + (resume_profile.get("internships") or [])
        ],
        "skills_they_are_missing": [item["skill"] for item in match["skills"]["missing"]],
        "skills_they_will_be_probed_on": [
            item["skill"] for item in match["skills"]["partial"]
        ],
    }
    if focus:
        context["extra_focus_requested_by_user"] = focus

    # Scale the request to what the provider can actually return in one
    # response. Asking a free-tier model for twenty questions with sample
    # answers gets JSON that's cut off mid-object and rejected outright.
    per_category = 2 if llm.compact_output else 4
    task = (
        f"Generate the interview preparation set with exactly {per_category} questions "
        "per category. Project and experience questions must reference only the "
        "projects and roles listed above, which come from the resume."
    )
    if llm.compact_output:
        task += (
            " Keep each sample_answer under 60 words and each expected_points entry "
            "to a single short phrase."
        )

    result = generate_grounded(
        llm,
        system=INTERVIEW_SYSTEM,
        task=task,
        chunks=chunks,
        schema=INTERVIEW_SCHEMA,
        effort=settings.llm_effort,
        max_tokens=12000,
    )

    questions: List[Dict[str, Any]] = []
    dropped = 0
    lowered_projects = {name.lower() for name in project_names}

    for index, question in enumerate(result.data.get("questions") or []):
        question["id"] = question.get("id") or f"q-{index + 1}"

        # Guard: a "project" question about a project that doesn't exist is a
        # hallucination, so drop it rather than show it.
        if question.get("category") == "project" and lowered_projects:
            related = str(question.get("related_to", "")).lower()
            body = str(question.get("question", "")).lower()
            if not any(
                name in related or name in body for name in lowered_projects
            ):
                dropped += 1
                continue

        question["category_label"] = CATEGORY_LABELS.get(
            question.get("category", ""), "Other"
        )
        questions.append(question)

    by_category: Dict[str, List[Dict[str, Any]]] = {key: [] for key in CATEGORY_LABELS}
    for question in questions:
        by_category.setdefault(question.get("category", "technical"), []).append(question)

    payload = {
        "questions": questions,
        "by_category": by_category,
        "categories": [
            {"key": key, "label": label, "count": len(by_category.get(key, []))}
            for key, label in CATEGORY_LABELS.items()
        ],
        "preparation_focus": result.data.get("preparation_focus") or [],
        "sources": result.sources,
        "job_title": jd_profile.get("job_title", ""),
        "dropped_unverified": dropped,
        "total": len(questions),
    }

    store.save_analysis(session_id, cache_key, payload)
    return payload
