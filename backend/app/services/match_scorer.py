"""Resume <-> Job Description match scoring.

**Every number on the dashboard is computed here, in Python.** The LLM is
called afterwards and is explicitly told the scores are final. That design
choice matters:

* the same resume and JD always produce the same score;
* every score ships with the arithmetic that produced it;
* the model can't quietly award marks for something the resume doesn't say.

The five components and their weights:

    Skills      35%   weighted coverage of required + preferred skills
    Projects    20%   embedding similarity of projects to job requirements
    Experience  18%   years vs. required, plus responsibility alignment
    Keywords    17%   ATS keyword coverage, weighted by prominence
    Education   10%   degree level vs. requirement, plus field relevance

Overall = the weighted sum of those five.
"""

import re
from typing import Any, Dict, List, Optional

from app.core.config import Settings
from app.core.logging import get_logger
from app.models.store import Store
from app.rag.generation import generate_grounded
from app.rag.llm import get_llm
from app.rag.prompts import MATCH_EXPLAIN_SCHEMA, MATCH_EXPLAIN_SYSTEM, json_block
from app.rag.retriever import Retriever, get_retriever
from app.services import ats as ats_service
from app.services import project_ranker
from app.services.jd_analyzer import get_jd_profile
from app.services.resume_analyzer import all_resume_skills, get_resume_profile
from app.services.skill_matching import (
    SkillMatch,
    classify_all,
    extra_resume_skills,
    normalize_alignment,
)

logger = get_logger(__name__)

ANALYSIS_KIND = "match"

WEIGHTS = {
    "skills": 0.35,
    "projects": 0.20,
    "experience": 0.18,
    "keywords": 0.17,
    "education": 0.10,
}

DEGREE_LEVELS = [
    (5, ["ph.d", "phd", "doctorate", "doctoral"]),
    (4, ["m.tech", "mtech", "m.e.", "master", "msc", "m.sc", "ms in", "mba", "mca", "m.s."]),
    (3, ["b.tech", "btech", "b.e.", "bachelor", "bsc", "b.sc", "bs in", "bca", "b.s.",
         "undergraduate", "engineering degree"]),
    (2, ["diploma", "associate"]),
    (1, ["high school", "12th", "intermediate", "hsc"]),
]

STEM_FIELDS = [
    "computer", "software", "information technology", "it", "electronics",
    "electrical", "engineering", "data science", "statistics", "mathematics",
    "cs", "ece", "information systems", "computer applications",
]


def _degree_level(text: str) -> int:
    lowered = text.lower()
    for level, markers in DEGREE_LEVELS:
        if any(marker in lowered for marker in markers):
            return level
    return 0


def _level_name(level: int) -> str:
    return {5: "Doctorate", 4: "Master's", 3: "Bachelor's", 2: "Diploma", 1: "High school"}.get(
        level, "unspecified"
    )


# --------------------------------------------------------------------------
# Individual components
# --------------------------------------------------------------------------
def score_skills(matches: List[SkillMatch]) -> Dict[str, Any]:
    if not matches:
        return {
            "score": 0,
            "calculation": "The job description listed no skills we could extract.",
            "details": {"matched": 0, "partial": 0, "missing": 0, "total": 0},
        }

    earned = sum(match.weight * match.credit for match in matches)
    possible = sum(match.weight for match in matches)
    score = round(100 * earned / possible) if possible else 0

    matched = [m for m in matches if m.status == "matched"]
    partial = [m for m in matches if m.status == "partial"]
    missing = [m for m in matches if m.status == "missing"]
    required = [m for m in matches if m.importance == "required"]

    calculation = (
        f"{len(matches)} skills were extracted from the job description "
        f"({len(required)} required, {len(matches) - len(required)} preferred). "
        f"Required skills count 1.0, preferred count 0.4. A fully evidenced skill "
        f"earns full credit, a partially evidenced one earns half, a missing one "
        f"earns nothing. You have {len(matched)} matched, {len(partial)} partial and "
        f"{len(missing)} missing, giving {earned:.1f} of {possible:.1f} "
        f"weighted points = {score}%."
    )

    return {
        "score": score,
        "calculation": calculation,
        "details": {
            "matched": len(matched),
            "partial": len(partial),
            "missing": len(missing),
            "total": len(matches),
            "required_total": len(required),
            "required_matched": len([m for m in required if m.status == "matched"]),
        },
    }


def score_experience(
    resume_profile: Dict[str, Any],
    jd_profile: Dict[str, Any],
    session_id: str,
    retriever: Retriever,
) -> Dict[str, Any]:
    required_years = float(jd_profile.get("min_experience_years") or 0)
    actual_years = float(resume_profile.get("total_experience_years") or 0)

    responsibilities = [
        str(item) for item in (jd_profile.get("responsibilities") or []) if str(item).strip()
    ]
    is_semantic = bool(retriever.embedder_info.get("semantic"))

    # How well does the resume cover what the job actually involves day to day?
    if responsibilities:
        raw_scores = [
            retriever.max_similarity_to_text(session_id, responsibility, doc_type="resume")
            for responsibility in responsibilities
        ]
        raw_mean = sum(raw_scores) / len(raw_scores)
        alignment = normalize_alignment(raw_mean, is_semantic, kind="requirement")
        covered = sum(
            1
            for score in raw_scores
            if normalize_alignment(score, is_semantic, kind="requirement") >= 0.5
        )
    else:
        raw_mean, alignment, covered = 0.0, 0.5, 0

    if required_years <= 0:
        years_component = 1.0
        years_note = "The job description states no minimum years of experience, so this isn't a gap."
    else:
        years_component = min(1.0, actual_years / required_years)
        years_note = (
            f"The job asks for {required_years:g} year(s); your resume shows about "
            f"{actual_years:g} year(s) of dated roles and internships "
            f"({years_component * 100:.0f}% of the requirement)."
        )

    score = round(100 * (0.55 * years_component + 0.45 * alignment))

    calculation = (
        f"{years_note} Separately, each of the {len(responsibilities)} responsibilities "
        f"in the posting was compared semantically against your resume (mean similarity "
        f"{raw_mean:.3f}, {covered} of {len(responsibilities)} clearly covered). "
        f"Final = 55% x years ({years_component * 100:.0f}%) + 45% x responsibility "
        f"alignment ({alignment * 100:.0f}%) = {score}%."
    )

    return {
        "score": score,
        "calculation": calculation,
        "details": {
            "required_years": required_years,
            "actual_years": actual_years,
            "responsibilities_total": len(responsibilities),
            "responsibilities_covered": covered,
            "alignment": round(alignment, 3),
        },
    }


def score_education(
    resume_profile: Dict[str, Any], jd_profile: Dict[str, Any]
) -> Dict[str, Any]:
    requirements = [
        str(item) for item in (jd_profile.get("education_requirements") or []) if str(item).strip()
    ]
    education = resume_profile.get("education") or []

    resume_level = 0
    resume_field = ""
    for entry in education:
        combined = f"{entry.get('degree', '')} {entry.get('field', '')}"
        level = _degree_level(combined)
        if level > resume_level:
            resume_level = level
            resume_field = f"{entry.get('degree', '')} {entry.get('field', '')}".strip()

    required_level = max((_degree_level(item) for item in requirements), default=0)

    if not requirements:
        return {
            "score": 100,
            "calculation": (
                "The job description doesn't state an education requirement, so this "
                "component can't count against you. Scored 100%."
            ),
            "details": {"required": "none stated", "yours": resume_field or "not detected"},
        }

    if resume_level == 0:
        score = 40 if education else 0
        calculation = (
            f"The job asks for: {requirements[0]}. We couldn't identify a degree level "
            f"in your resume's education section, so this is scored conservatively at {score}%."
        )
        return {
            "score": score,
            "calculation": calculation,
            "details": {"required": requirements[0], "yours": resume_field or "not detected"},
        }

    if required_level == 0:
        base = 0.9
        level_note = "The requirement doesn't name a specific degree level."
    elif resume_level >= required_level:
        base = 1.0
        level_note = (
            f"You hold a {_level_name(resume_level)} and the job requires a "
            f"{_level_name(required_level)} -- requirement met."
        )
    elif resume_level == required_level - 1:
        base = 0.6
        level_note = (
            f"The job requires a {_level_name(required_level)}; your highest is a "
            f"{_level_name(resume_level)} -- one level short."
        )
    else:
        base = 0.3
        level_note = (
            f"The job requires a {_level_name(required_level)}; your highest is a "
            f"{_level_name(resume_level)}."
        )

    requirement_text = " ".join(requirements).lower()
    wants_stem = any(field in requirement_text for field in STEM_FIELDS)
    has_stem = any(field in resume_field.lower() for field in STEM_FIELDS)
    if wants_stem and not has_stem:
        base *= 0.85
        field_note = " Your field of study doesn't clearly match the field the posting names."
    elif wants_stem and has_stem:
        field_note = " Your field of study matches what the posting asks for."
    else:
        field_note = ""

    score = round(100 * base)
    return {
        "score": score,
        "calculation": level_note + field_note + f" Scored {score}%.",
        "details": {
            "required": requirements[0],
            "yours": resume_field or "not detected",
            "required_level": _level_name(required_level),
            "your_level": _level_name(resume_level),
        },
    }


# --------------------------------------------------------------------------
# The full report
# --------------------------------------------------------------------------
def _build_components(
    skills: Dict[str, Any],
    projects: Dict[str, Any],
    experience: Dict[str, Any],
    keywords: Dict[str, Any],
    education: Dict[str, Any],
) -> List[Dict[str, Any]]:
    labels = {
        "skills": "Skills Match",
        "projects": "Project Match",
        "experience": "Experience Match",
        "keywords": "Keyword Match",
        "education": "Education Match",
    }
    raw = {
        "skills": skills,
        "projects": projects,
        "experience": experience,
        "keywords": keywords,
        "education": education,
    }
    return [
        {
            "key": key,
            "label": labels[key],
            "score": raw[key]["score"],
            "weight": WEIGHTS[key],
            "weight_percent": round(WEIGHTS[key] * 100),
            "contribution": round(raw[key]["score"] * WEIGHTS[key], 1),
            "calculation": raw[key]["calculation"],
            "details": raw[key].get("details", {}),
        }
        for key in ("skills", "projects", "experience", "keywords", "education")
    ]


def compute_match(
    session_id: str,
    settings: Settings,
    store: Store,
    *,
    refresh: bool = False,
) -> Dict[str, Any]:
    """Compute (or fetch from cache) the full match report."""
    if not refresh:
        cached = store.get_analysis(session_id, ANALYSIS_KIND)
        if cached:
            return cached

    resume_profile = get_resume_profile(session_id, settings, store)
    jd_profile = get_jd_profile(session_id, settings, store)
    retriever = get_retriever(settings)

    resume_document = store.get_document(session_id, "resume") or {}
    resume_text = resume_document.get("text", "")
    resume_chunks = store.list_chunks(session_id, doc_type="resume")

    # ---- 1. skills ------------------------------------------------------
    skill_matches = classify_all(
        jd_profile.get("required_skills") or [],
        jd_profile.get("preferred_skills") or [],
        session_id=session_id,
        retriever=retriever,
        resume_text=resume_text,
        resume_chunks=resume_chunks,
    )
    skills_component = score_skills(skill_matches)

    # ---- 2. projects ----------------------------------------------------
    ranked_projects = project_ranker.rank_projects(
        resume_profile.get("projects") or [], jd_profile, retriever
    )
    project_value = project_ranker.project_score(ranked_projects)
    if ranked_projects:
        best = ranked_projects[0]
        projects_component = {
            "score": round(100 * project_value),
            "calculation": (
                f"Each of your {len(ranked_projects)} projects was embedded and compared "
                f"against the job's responsibilities and required skills. The component "
                f"score is the average relevance of your {min(3, len(ranked_projects))} "
                f"strongest projects (best: '{best['name']}' at {best['relevance']}%) = "
                f"{round(100 * project_value)}%."
            ),
            "details": {"project_count": len(ranked_projects), "best": best["name"]},
        }
    else:
        projects_component = {
            "score": 0,
            "calculation": (
                "No projects were found in your resume, so there is nothing to compare "
                "against the job's requirements. Scored 0%."
            ),
            "details": {"project_count": 0},
        }

    # ---- 3. experience --------------------------------------------------
    experience_component = score_experience(resume_profile, jd_profile, session_id, retriever)

    # ---- 4. keywords (ATS) ----------------------------------------------
    ats_report = ats_service.analyze_keywords(
        jd_profile.get("keywords") or [], resume_text, resume_chunks
    )
    keywords_component = {
        "score": ats_report["score"],
        "calculation": ats_report["calculation"],
        "details": {
            "matched": ats_report["matched_count"],
            "missing": ats_report["missing_count"],
            "total": ats_report["total"],
        },
    }

    # ---- 5. education ---------------------------------------------------
    education_component = score_education(resume_profile, jd_profile)

    components = _build_components(
        skills_component, projects_component, experience_component,
        keywords_component, education_component,
    )
    overall = round(sum(component["contribution"] for component in components))

    formula = " + ".join(
        f"{component['label']} {component['score']}% x {component['weight_percent']}%"
        for component in components
    )

    report: Dict[str, Any] = {
        "overall": overall,
        "verdict_band": _band(overall),
        "components": components,
        "formula": f"Overall = {formula} = {overall}%",
        "skills": {
            "matched": [_skill_dict(m) for m in skill_matches if m.status == "matched"],
            "partial": [_skill_dict(m) for m in skill_matches if m.status == "partial"],
            "missing": [_skill_dict(m) for m in skill_matches if m.status == "missing"],
            "extra": extra_resume_skills(
                all_resume_skills(resume_profile),
                (jd_profile.get("required_skills") or []) + (jd_profile.get("preferred_skills") or []),
            ),
        },
        "projects": ranked_projects,
        "ats": ats_report,
        "job_title": jd_profile.get("job_title", ""),
        "company": jd_profile.get("company", ""),
        "candidate_name": resume_profile.get("name", ""),
        "method": {
            "weights": WEIGHTS,
            "embedding_model": retriever.embedder_info,
            "vector_store": retriever.store_info,
            "note": (
                "Scores are computed by deterministic Python, not by the language "
                "model. The model is given the finished numbers and asked only to "
                "explain them."
            ),
        },
    }

    # ---- LLM explanation layer -----------------------------------------
    report.update(_explain(report, session_id, settings, jd_profile))

    store.save_analysis(session_id, ANALYSIS_KIND, report)
    return report


def _band(overall: int) -> str:
    if overall >= 80:
        return "strong"
    if overall >= 65:
        return "good"
    if overall >= 45:
        return "moderate"
    return "weak"


def _skill_dict(match: SkillMatch) -> Dict[str, Any]:
    return {
        "skill": match.skill,
        "importance": match.importance,
        "status": match.status,
        "reason": match.reason,
        "evidence": match.evidence_text,
        "citation": match.evidence_citation,
        "chunk_id": match.evidence_chunk_id,
        "sections": match.evidence_sections,
        "mentions": match.mention_count,
        "similarity": match.semantic_score,
    }


def _explain(
    report: Dict[str, Any],
    session_id: str,
    settings: Settings,
    jd_profile: Dict[str, Any],
) -> Dict[str, Any]:
    """Ask the LLM to explain the already-computed report, grounded in chunks."""
    retriever = get_retriever(settings)
    llm = get_llm(settings)

    query = " ".join(
        filter(
            None,
            [
                jd_profile.get("job_title", ""),
                " ".join((jd_profile.get("required_skills") or [])[:8]),
                " ".join((jd_profile.get("responsibilities") or [])[:3]),
            ],
        )
    ) or "job requirements and candidate background"

    chunks = retriever.retrieve_pair(session_id, query, resume_k=6, jd_k=5)

    summary = {
        "overall_score": report["overall"],
        "components": [
            {
                "name": component["label"],
                "score": component["score"],
                "weight_percent": component["weight_percent"],
                "how_it_was_calculated": component["calculation"],
            }
            for component in report["components"]
        ],
        "matched_skills": [item["skill"] for item in report["skills"]["matched"]],
        "partial_skills": [item["skill"] for item in report["skills"]["partial"]],
        "missing_skills": [item["skill"] for item in report["skills"]["missing"]],
        "top_projects": [
            {"name": item["name"], "relevance": item["relevance"]}
            for item in report["projects"][:3]
        ],
        "missing_keywords": report["ats"]["missing"][:12],
    }

    task = (
        "Explain this match report to the candidate. Use the CONTEXT passages as your "
        "only source of facts about the resume and the job. Do not restate the numbers "
        "as if you chose them, and do not contradict them."
    )

    try:
        result = generate_grounded(
            llm,
            system=MATCH_EXPLAIN_SYSTEM,
            task=task,
            chunks=chunks,
            schema=MATCH_EXPLAIN_SCHEMA,
            effort=settings.llm_effort,
            extra_context=json_block("ALREADY-CALCULATED MATCH REPORT (final, do not change)", summary),
        )
    except Exception as exc:
        # The scores are still perfectly valid without the prose layer.
        logger.warning("Match explanation failed (%s); returning scores without prose.", exc)
        return {
            "verdict": "",
            "explanations": {},
            "strengths": [],
            "gaps": [],
            "sources": [],
            "explanation_available": False,
        }

    return {
        "verdict": result.data.get("overall_verdict", ""),
        "explanations": result.data.get("explanations", {}),
        "strengths": result.data.get("strengths", []),
        "gaps": result.data.get("gaps", []),
        "sources": result.sources,
        "explanation_available": True,
    }
