"""Explanation layer for project relevance.

The ranking itself is computed with embeddings in `project_ranker`. This
service asks the LLM to explain a ranking it did not choose, grounded in the
retrieved project and requirement chunks.
"""

from typing import Any, Dict, List

from app.core.config import Settings
from app.core.logging import get_logger
from app.models.store import Store
from app.rag.generation import generate_grounded
from app.rag.llm import get_llm
from app.rag.prompts import PROJECT_RELEVANCE_SCHEMA, PROJECT_RELEVANCE_SYSTEM, json_block
from app.rag.retriever import get_retriever
from app.services.jd_analyzer import get_jd_profile
from app.services.match_scorer import compute_match

logger = get_logger(__name__)

ANALYSIS_KIND = "project_insights"


def explain_projects(
    session_id: str, settings: Settings, store: Store, *, refresh: bool = False
) -> Dict[str, Any]:
    if not refresh:
        cached = store.get_analysis(session_id, ANALYSIS_KIND)
        if cached:
            return cached

    match = compute_match(session_id, settings, store)
    ranked: List[Dict[str, Any]] = match.get("projects") or []

    if not ranked:
        payload = {"projects": [], "sources": [], "note": "No projects were found in your resume."}
        store.save_analysis(session_id, ANALYSIS_KIND, payload)
        return payload

    jd_profile = get_jd_profile(session_id, settings, store)
    retriever = get_retriever(settings)
    llm = get_llm(settings)

    query = " ".join(
        [item["name"] for item in ranked[:5]]
        + (jd_profile.get("required_skills") or [])[:6]
        + [jd_profile.get("job_title", "")]
    )
    chunks = retriever.retrieve_pair(
        session_id, query, resume_k=6, jd_k=5
    )

    handoff = {
        "job_title": jd_profile.get("job_title", ""),
        "projects": [
            {
                "name": item["name"],
                "relevance_percent": item["relevance"],
                "technologies": item["technologies"],
                "matching_technologies": item["matching_technologies"],
                "closest_job_requirements": [
                    requirement["requirement"] for requirement in item["top_requirements"]
                ],
            }
            for item in ranked
        ],
    }

    task = (
        "For every project listed in the ranking, explain why it earned that relevance "
        "score for this specific job. Return one entry per project, using the exact "
        "project names given. Do not change any percentage."
    )

    try:
        result = generate_grounded(
            llm,
            system=PROJECT_RELEVANCE_SYSTEM,
            task=task,
            chunks=chunks,
            schema=PROJECT_RELEVANCE_SCHEMA,
            effort=settings.llm_effort,
            extra_context=json_block("COMPUTED PROJECT RANKING (final, do not change)", handoff),
        )
        explanations = {
            str(item.get("name", "")).strip().lower(): item
            for item in (result.data.get("projects") or [])
        }
        sources = result.sources
    except Exception as exc:
        logger.warning("Project explanations failed (%s); returning ranking only.", exc)
        explanations, sources = {}, []

    merged = []
    for item in ranked:
        explanation = explanations.get(item["name"].strip().lower(), {})
        merged.append(
            {
                **item,
                "why_relevant": explanation.get("why_relevant", ""),
                "matching_requirements": explanation.get("matching_requirements", []),
                "what_to_emphasize": explanation.get("what_to_emphasize", ""),
            }
        )

    payload = {"projects": merged, "sources": sources, "note": ""}
    store.save_analysis(session_id, ANALYSIS_KIND, payload)
    return payload
