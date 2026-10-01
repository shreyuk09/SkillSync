"""The "What should I change?" action plan.

Takes the computed match report and turns it into four prioritised buckets:
high / medium / low / already strong.
"""

from typing import Any, Dict

from app.core.config import Settings
from app.core.logging import get_logger
from app.models.store import Store
from app.rag.generation import generate_grounded
from app.rag.llm import get_llm
from app.rag.prompts import PRIORITIES_SCHEMA, PRIORITIES_SYSTEM, json_block
from app.rag.retriever import get_retriever
from app.services.jd_analyzer import get_jd_profile
from app.services.match_scorer import compute_match

logger = get_logger(__name__)

ANALYSIS_KIND = "priorities"


def generate_priorities(
    session_id: str, settings: Settings, store: Store, *, refresh: bool = False
) -> Dict[str, Any]:
    if not refresh:
        cached = store.get_analysis(session_id, ANALYSIS_KIND)
        if cached:
            return cached

    match = compute_match(session_id, settings, store)
    jd_profile = get_jd_profile(session_id, settings, store)
    retriever = get_retriever(settings)
    llm = get_llm(settings)

    query = " ".join(
        [jd_profile.get("job_title", ""), "requirements gaps strengths"]
        + [item["skill"] for item in match["skills"]["missing"][:6]]
        + [item["skill"] for item in match["skills"]["partial"][:6]]
    )
    chunks = retriever.retrieve_pair(
        session_id, query, resume_k=7, jd_k=5
    )

    summary = {
        "job_title": jd_profile.get("job_title", ""),
        "overall_match": match["overall"],
        "component_scores": {
            component["key"]: component["score"] for component in match["components"]
        },
        "matched_skills": [item["skill"] for item in match["skills"]["matched"]],
        "partial_skills": [
            {"skill": item["skill"], "why": item["reason"]}
            for item in match["skills"]["partial"]
        ],
        "missing_required_skills": [
            item["skill"] for item in match["skills"]["missing"]
            if item["importance"] == "required"
        ],
        "missing_preferred_skills": [
            item["skill"] for item in match["skills"]["missing"]
            if item["importance"] == "preferred"
        ],
        "missing_ats_keywords": match["ats"]["high_priority_missing"],
        "project_ranking": [
            {"name": item["name"], "relevance": item["relevance"]}
            for item in (match.get("projects") or [])
        ],
        "computed_gaps": match.get("gaps", []),
    }

    task = (
        "Produce the prioritised action plan. Base every item on the analysis and the "
        "CONTEXT passages -- do not introduce facts from anywhere else."
    )

    result = generate_grounded(
        llm,
        system=PRIORITIES_SYSTEM,
        task=task,
        chunks=chunks,
        schema=PRIORITIES_SCHEMA,
        effort=settings.llm_effort,
        extra_context=json_block("COMPUTED MATCH ANALYSIS", summary),
    )

    payload = {
        "high": result.data.get("high", []),
        "medium": result.data.get("medium", []),
        "low": result.data.get("low", []),
        "already_strong": result.data.get("already_strong", []),
        "sources": result.sources,
        "overall_match": match["overall"],
        "job_title": jd_profile.get("job_title", ""),
    }

    store.save_analysis(session_id, ANALYSIS_KIND, payload)
    return payload
