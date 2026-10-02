"""Analysis endpoints.

These are declared as plain `def` (not `async def`) on purpose: FastAPI runs
sync handlers in a worker thread, which is exactly right for code that blocks
on the LLM API and on local embedding computation.

Results are cached per session, so navigating between pages doesn't re-bill an
LLM call. `?refresh=true` forces a recompute.
"""

from fastapi import APIRouter, Query

from app.api.deps import SessionDep, SettingsDep, StoreDep
from app.schemas.analysis import DecisionRequest
from app.services import improvements as improvements_service
from app.services import priorities as priorities_service
from app.services import projects as projects_service
from app.services.jd_analyzer import get_jd_profile
from app.services.match_scorer import compute_match
from app.services.resume_analyzer import get_resume_profile

router = APIRouter(prefix="/sessions/{session_id}/analysis", tags=["analysis"])

RefreshQuery = Query(default=False, description="Recompute instead of using the cache")


@router.get("/resume")
def resume_profile(
    session_id: SessionDep,
    settings: SettingsDep,
    store: StoreDep,
    refresh: bool = RefreshQuery,
):
    """Structured resume: skills, education, projects, experience, and more."""
    return get_resume_profile(session_id, settings, store, refresh=refresh)


@router.get("/job")
def jd_profile(
    session_id: SessionDep,
    settings: SettingsDep,
    store: StoreDep,
    refresh: bool = RefreshQuery,
):
    """Structured job description: required/preferred skills, responsibilities."""
    return get_jd_profile(session_id, settings, store, refresh=refresh)


@router.get("/match")
def match(
    session_id: SessionDep,
    settings: SettingsDep,
    store: StoreDep,
    refresh: bool = RefreshQuery,
):
    """The full match report: scores, skill buckets, ATS, project ranking."""
    return compute_match(session_id, settings, store, refresh=refresh)


@router.get("/skills")
def skills(
    session_id: SessionDep,
    settings: SettingsDep,
    store: StoreDep,
    refresh: bool = RefreshQuery,
):
    """Just the matched / partial / missing skill breakdown."""
    report = compute_match(session_id, settings, store, refresh=refresh)
    return {
        **report["skills"],
        "score": next(
            component["score"]
            for component in report["components"]
            if component["key"] == "skills"
        ),
        "calculation": next(
            component["calculation"]
            for component in report["components"]
            if component["key"] == "skills"
        ),
    }


@router.get("/ats")
def ats(
    session_id: SessionDep,
    settings: SettingsDep,
    store: StoreDep,
    refresh: bool = RefreshQuery,
):
    """ATS keyword coverage."""
    return compute_match(session_id, settings, store, refresh=refresh)["ats"]


@router.get("/projects")
def projects(
    session_id: SessionDep,
    settings: SettingsDep,
    store: StoreDep,
    refresh: bool = RefreshQuery,
):
    """Project relevance ranking, with an explanation for each project."""
    return projects_service.explain_projects(session_id, settings, store, refresh=refresh)


@router.get("/improvements")
def improvements(
    session_id: SessionDep,
    settings: SettingsDep,
    store: StoreDep,
    refresh: bool = RefreshQuery,
):
    """Before/after rewrite suggestions, each verified against the resume."""
    return improvements_service.generate_improvements(
        session_id, settings, store, refresh=refresh
    )


@router.post("/improvements/decision")
def improvement_decision(
    session_id: SessionDep,
    payload: DecisionRequest,
    store: StoreDep,
):
    """Accept or reject one suggestion."""
    decisions = improvements_service.set_decision(
        session_id, payload.suggestion_id, payload.decision, store
    )
    return {"ok": True, "decisions": decisions}


@router.get("/priorities")
def priorities(
    session_id: SessionDep,
    settings: SettingsDep,
    store: StoreDep,
    refresh: bool = RefreshQuery,
):
    """The 'What should I change?' prioritised plan."""
    return priorities_service.generate_priorities(session_id, settings, store, refresh=refresh)


@router.get("/dashboard")
def dashboard(
    session_id: SessionDep,
    settings: SettingsDep,
    store: StoreDep,
    refresh: bool = RefreshQuery,
):
    """Everything the dashboard needs, in one round trip."""
    report = compute_match(session_id, settings, store, refresh=refresh)
    resume = get_resume_profile(session_id, settings, store)
    job = get_jd_profile(session_id, settings, store)

    return {
        "overall": report["overall"],
        "verdict_band": report["verdict_band"],
        "verdict": report.get("verdict", ""),
        "formula": report["formula"],
        "components": report["components"],
        "explanations": report.get("explanations", {}),
        "strengths": report.get("strengths", []),
        "gaps": report.get("gaps", []),
        "sources": report.get("sources", []),
        "skills": report["skills"],
        "ats": {
            "score": report["ats"]["score"],
            "matched_count": report["ats"]["matched_count"],
            "missing_count": report["ats"]["missing_count"],
            "total": report["ats"]["total"],
            "high_priority_missing": report["ats"]["high_priority_missing"],
        },
        "projects": report["projects"][:5],
        "method": report["method"],
        "candidate": {
            "name": resume.get("name", ""),
            "completeness": resume.get("completeness", {}),
            "stats": resume.get("stats", {}),
        },
        "job": {
            "title": job.get("job_title", ""),
            "company": job.get("company", ""),
            "seniority": job.get("seniority", ""),
            "location": job.get("location", ""),
            "stats": job.get("stats", {}),
        },
    }
