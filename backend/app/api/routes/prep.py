"""Interview preparation and learning roadmap endpoints."""

from fastapi import APIRouter, Query

from app.api.deps import SessionDep, SettingsDep, StoreDep
from app.schemas.analysis import InterviewRequest, RoadmapRequest
from app.services import interview as interview_service
from app.services import roadmap as roadmap_service

router = APIRouter(prefix="/sessions/{session_id}", tags=["preparation"])


@router.get("/interview")
def get_interview(
    session_id: SessionDep,
    settings: SettingsDep,
    store: StoreDep,
    refresh: bool = Query(default=False),
):
    """Personalised interview questions across five categories."""
    return interview_service.generate_interview_prep(
        session_id, settings, store, refresh=refresh
    )


@router.post("/interview")
def post_interview(
    session_id: SessionDep,
    payload: InterviewRequest,
    settings: SettingsDep,
    store: StoreDep,
):
    """Regenerate interview questions, optionally focused on one topic."""
    return interview_service.generate_interview_prep(
        session_id, settings, store, refresh=payload.refresh, focus=payload.focus
    )


@router.get("/roadmap")
def get_roadmap(
    session_id: SessionDep,
    settings: SettingsDep,
    store: StoreDep,
    refresh: bool = Query(default=False),
):
    """A week-by-week plan built from the gaps the analysis found."""
    return roadmap_service.generate_roadmap(session_id, settings, store, refresh=refresh)


@router.post("/roadmap")
def post_roadmap(
    session_id: SessionDep,
    payload: RoadmapRequest,
    settings: SettingsDep,
    store: StoreDep,
):
    """Regenerate the roadmap, optionally with a specific number of weeks."""
    return roadmap_service.generate_roadmap(
        session_id, settings, store, refresh=payload.refresh, weeks=payload.weeks
    )
