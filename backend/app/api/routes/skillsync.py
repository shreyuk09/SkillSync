"""SkillSync dashboard API: resumes, jobs, matches, analysis, gaps,
improvements, chat. Everything except chat is deterministic and cached."""

from typing import Dict, List, Optional

from fastapi import APIRouter, File, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from app.api.deps import SettingsDep
from app.skillsync import engine, rag
from app.skillsync.dataset import get_dataset, get_job, get_resume
from app.skillsync.dataset import NotFound
from app.skillsync.jd_parser import delete_uploaded_job, parse_job_file, parse_job_text
from app.skillsync.parser import parse_resume
from app.utils.files import validate_upload

router = APIRouter(tags=["skillsync"])


def _resume_card(r: Dict) -> Dict:
    return {"id": r["id"], "name": r.get("name"), "headline": r.get("headline"), "target_role": r.get("target_role"),
            "location": r.get("location"), "years_experience": engine.years_of(r),
            "top_skills": r.get("skills", {}).get("technical", [])[:5], "source": r.get("source", {})}


@router.get("/resumes")
def list_resumes():
    ds = get_dataset()
    items = [_resume_card(r) for r in ds.resumes.values()]
    return {"version": ds.version, "samples": [i for i in items if i["source"].get("type") != "upload"],
            "uploads": [i for i in items if i["source"].get("type") == "upload"]}


@router.get("/resumes/{resume_id}")
def resume_detail(resume_id: str):
    r = get_resume(resume_id)
    return {**engine.profile(r), "completion": engine.completion(r)}


@router.post("/resume/upload")
async def upload_resume(settings: SettingsDep, file: UploadFile = File(...)):
    content = await file.read(settings.max_upload_bytes + 1)
    safe_name, extension = validate_upload(file.filename or "resume", content, settings)
    resume = await run_in_threadpool(parse_resume, content, safe_name, extension)
    return {"resume": _resume_card(resume), "id": resume["id"]}


@router.get("/jobs")
def list_jobs():
    ds = get_dataset()
    return {"roles": [{k: r[k] for k in ("role", "title", "summary", "core_skills", "posting_ids")} for r in ds.roles.values()],
            "jobs": [engine.job_card(j) for j in ds.jobs.values()]}


@router.post("/jobs/upload")
async def upload_job(settings: SettingsDep, file: UploadFile = File(...)):
    """Upload your own job description (PDF, DOCX, TXT or image)."""
    content = await file.read(settings.max_upload_bytes + 1)
    safe_name, extension = validate_upload(file.filename or "job-description", content, settings)
    job = await run_in_threadpool(parse_job_file, content, safe_name, extension)
    return {"id": job["id"], "job": engine.job_card(get_job(job["id"]))}


class JobText(BaseModel):
    text: str = Field(min_length=60, max_length=40000)


@router.post("/jobs/upload-text")
async def upload_job_text(req: JobText):
    job = await run_in_threadpool(parse_job_text, req.text)
    return {"id": job["id"], "job": engine.job_card(get_job(job["id"]))}


@router.delete("/jobs/{job_id}")
def delete_job(job_id: str):
    if not delete_uploaded_job(job_id):
        raise NotFound("Only job descriptions you uploaded can be removed.")
    return {"deleted": job_id}


@router.get("/jobs/{job_id}")
def job(job_id: str, resume_id: Optional[str] = None):
    if resume_id:
        return engine.job_detail(resume_id, job_id)
    j = get_job(job_id)
    return {**engine.job_card(j), "responsibilities": j.get("responsibilities", []), "requirements": j.get("requirements", [])}


@router.get("/matches/{resume_id}")
def matches(resume_id: str):
    return {"resume_id": resume_id, "matches": engine.matches(resume_id), "strong_threshold": engine.STRONG_MATCH}


@router.get("/analysis/{resume_id}")
def analysis(resume_id: str):
    return engine.analysis(resume_id)


@router.get("/skills/{resume_id}")
def skills(resume_id: str, role: Optional[str] = None, job_id: Optional[str] = None):
    return engine.gaps(resume_id, role, job_id)


@router.get("/improvements/{resume_id}")
def improvements(resume_id: str):
    return engine.improvements(resume_id)


@router.get("/dashboard/{resume_id}")
def dashboard(resume_id: str):
    return engine.dashboard(resume_id)


class ChatTurn(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=600)
    resume_id: str
    job_id: Optional[str] = None
    history: List[ChatTurn] = []


@router.post("/chat")
async def chat(req: ChatRequest):
    get_resume(req.resume_id)
    return await run_in_threadpool(rag.chat, req.question, req.resume_id, req.job_id, [h.model_dump() for h in req.history])


class QueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=600)
    resume_id: str
    job_id: Optional[str] = None
    k: int = Field(default=6, ge=1, le=12)


@router.post("/rag/query")
async def rag_query(req: QueryRequest):
    get_resume(req.resume_id)
    hits = await run_in_threadpool(rag.retrieve, req.query, req.resume_id, req.job_id, req.k)
    return {"query": req.query, "results": hits}


@router.get("/rag/status")
def rag_status():
    return {"ready": rag.is_ready()}
