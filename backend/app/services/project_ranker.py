"""Project relevance ranking -- pure vector similarity.

For every project in the resume we build a small document (name + description
+ technologies + highlights), embed it, and compare it against embeddings of
every job requirement (responsibilities + required skills).

Relevance = the mean of the project's top-N similarities to those
requirements, rescaled to a readable 0-100. Taking the top N rather than the
average over *all* requirements matters: a project should be judged on the
requirements it does address, not penalised for the ones it was never about.

The LLM never picks the ranking. It is asked afterwards to explain a ranking it
was handed, which is why the percentages stay stable between runs.
"""

from typing import Any, Dict, List

import numpy as np

from app.rag.retriever import Retriever
from app.services.skill_matching import canonical_skill, normalize_alignment

TOP_N_REQUIREMENTS = 4


def _project_document(project: Dict[str, Any]) -> str:
    parts = [
        project.get("name", ""),
        project.get("description", ""),
        " ".join(project.get("technologies") or []),
        " ".join(project.get("highlights") or []),
    ]
    return ". ".join(part.strip() for part in parts if str(part).strip())


def rank_projects(
    projects: List[Dict[str, Any]],
    jd_profile: Dict[str, Any],
    retriever: Retriever,
) -> List[Dict[str, Any]]:
    """Rank resume projects by relevance to the job. Returns highest first."""
    if not projects:
        return []

    requirements: List[str] = []
    requirement_kinds: List[str] = []

    for responsibility in jd_profile.get("responsibilities") or []:
        if str(responsibility).strip():
            requirements.append(str(responsibility).strip())
            requirement_kinds.append("responsibility")

    for skill in jd_profile.get("required_skills") or []:
        if str(skill).strip():
            requirements.append(f"Required skill: {skill}")
            requirement_kinds.append("required skill")

    if not requirements:
        # A JD with no parsed requirements: fall back to its summary.
        summary = jd_profile.get("summary") or jd_profile.get("job_title") or "the role"
        requirements = [str(summary)]
        requirement_kinds = ["role summary"]

    project_texts = [_project_document(project) for project in projects]
    project_vectors = retriever.embed_many(project_texts)
    requirement_vectors = retriever.embed_many(requirements)

    def unit(matrix: np.ndarray) -> np.ndarray:
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        return matrix / np.clip(norms, 1e-9, None)

    # (projects x requirements) cosine similarity in one matrix multiply.
    similarity = unit(project_vectors) @ unit(requirement_vectors).T

    is_semantic = bool(retriever.embedder_info.get("semantic"))
    jd_skills = [
        canonical_skill(skill)
        for skill in (jd_profile.get("required_skills") or [])
        + (jd_profile.get("preferred_skills") or [])
    ]

    results: List[Dict[str, Any]] = []
    for index, project in enumerate(projects):
        row = similarity[index]
        top_count = min(TOP_N_REQUIREMENTS, len(requirements))
        top_indices = np.argsort(row)[::-1][:top_count]
        raw = float(np.mean(row[top_indices]))
        relevance = round(100 * normalize_alignment(raw, is_semantic, kind="requirement"))

        top_requirements = [
            {
                "requirement": requirements[i],
                "kind": requirement_kinds[i],
                "similarity": round(float(row[i]), 3),
            }
            for i in top_indices
        ]

        project_techs = [canonical_skill(t) for t in (project.get("technologies") or [])]
        overlapping = sorted(
            {
                tech
                for tech in (project.get("technologies") or [])
                if canonical_skill(tech) in jd_skills
            }
        )

        results.append(
            {
                "name": project.get("name") or f"Project {index + 1}",
                "description": project.get("description", ""),
                "technologies": project.get("technologies") or [],
                "highlights": project.get("highlights") or [],
                "relevance": relevance,
                "raw_similarity": round(raw, 4),
                "matching_technologies": overlapping,
                "top_requirements": top_requirements,
                "calculation": (
                    f"Averaged this project's embedding similarity against its "
                    f"{top_count} closest job requirements (raw cosine {raw:.3f}), "
                    f"then rescaled to {relevance}%."
                ),
            }
        )

    results.sort(key=lambda item: item["relevance"], reverse=True)
    return results


def project_score(ranked: List[Dict[str, Any]], top_n: int = 3) -> float:
    """Overall project-match component: the mean of the best `top_n` projects."""
    if not ranked:
        return 0.0
    best = [item["relevance"] for item in ranked[:top_n]]
    return sum(best) / len(best) / 100.0
