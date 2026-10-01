"""Load the editable SkillSync dataset from /data, reloading when files change.

    data/index.json            -- lists the resumes and job files
    data/skills.json           -- skill knowledge base
    data/resumes/*.json        -- sample resumes (synthetic)
    data/jobs/<role>.json      -- role summary + real postings (summarised)
    data/storage/uploads/*.json -- resumes the user uploaded (parsed)

The cache key is the modification time of every file, so editing any JSON file
is picked up on the next request without a restart.
"""

import hashlib
import json
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.logging import get_logger

logger = get_logger(__name__)


class NotFound(AppError):
    code = "not_found"
    status_code = 404


@dataclass
class Dataset:
    version: str
    resumes: Dict[str, Dict[str, Any]]
    roles: Dict[str, Dict[str, Any]]
    jobs: Dict[str, Dict[str, Any]]
    skills: Dict[str, Dict[str, Any]]
    kb_version: str = ""  # hash of the sample jobs + skills (drives the shared KB index)
    jobs_version: str = ""  # kb_version plus the user's uploaded job descriptions
    uploaded_jobs: List[str] = field(default_factory=list)
    resume_hashes: Dict[str, str] = field(default_factory=dict)


_lock = threading.Lock()
_cache: Optional[Tuple[Tuple, Dataset]] = None


def data_dir() -> Path:
    return get_settings().data_dir


def uploads_dir() -> Path:
    path = get_settings().storage_dir / "uploads"
    path.mkdir(parents=True, exist_ok=True)
    return path


def job_uploads_dir() -> Path:
    path = get_settings().storage_dir / "uploads" / "jobs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _files() -> List[Path]:
    root = data_dir()
    files = [root / "index.json", root / "skills.json"]
    files += sorted((root / "resumes").glob("*.json"))
    files += sorted((root / "jobs").glob("*.json"))
    files += sorted(uploads_dir().glob("*.json"))
    files += sorted(job_uploads_dir().glob("*.json"))
    return [f for f in files if f.exists()]


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # a typo in a hand-edited file shouldn't 500 everything
        logger.error("Could not read %s: %s", path, exc)
        return None


def _hash(obj: Any) -> str:
    return hashlib.sha1(json.dumps(obj, sort_keys=True).encode()).hexdigest()[:12]


def _load() -> Dataset:
    root = data_dir()
    skills_doc = _read(root / "skills.json") or {"skills": []}
    skills = {s["name"]: s for s in skills_doc.get("skills", [])}

    roles: Dict[str, Dict[str, Any]] = {}
    jobs: Dict[str, Dict[str, Any]] = {}
    for path in sorted((root / "jobs").glob("*.json")):
        doc = _read(path)
        if not doc:
            continue
        role = doc.get("role") or path.stem
        roles[role] = {
            "role": role,
            "title": doc.get("role_title", role),
            "summary": doc.get("role_summary", ""),
            "core_skills": doc.get("core_skills", []),
            "posting_ids": [p["id"] for p in doc.get("postings", [])],
        }
        for posting in doc.get("postings", []):
            jobs[posting["id"]] = {**posting, "role": role, "role_title": roles[role]["title"]}

    resumes: Dict[str, Dict[str, Any]] = {}
    for path in sorted((root / "resumes").glob("*.json")) + sorted(uploads_dir().glob("*.json")):
        doc = _read(path)
        if doc and doc.get("id"):
            resumes[doc["id"]] = doc

    kb_version = _hash([roles, jobs, skills])

    # Job descriptions the user uploaded. They join the job list (so they are
    # matched, compared and chat-able) but not the role statistics, which
    # stay based on the curated sample postings.
    uploaded: List[str] = []
    for path in sorted(job_uploads_dir().glob("*.json")):
        doc = _read(path)
        if doc and doc.get("id") and doc.get("role") in roles:
            jobs[doc["id"]] = {**doc, "role_title": roles[doc["role"]]["title"], "uploaded": True}
            uploaded.append(doc["id"])
    jobs_version = _hash([kb_version, [jobs[j] for j in uploaded]])
    resume_hashes = {rid: _hash(r) for rid, r in resumes.items()}
    return Dataset(
        version=_hash([jobs_version, resume_hashes]),
        resumes=resumes,
        roles=roles,
        jobs=jobs,
        skills=skills,
        kb_version=kb_version,
        jobs_version=jobs_version,
        uploaded_jobs=uploaded,
        resume_hashes=resume_hashes,
    )


def get_dataset() -> Dataset:
    global _cache
    stamp = tuple((str(f), f.stat().st_mtime_ns) for f in _files())
    if _cache and _cache[0] == stamp:
        return _cache[1]
    with _lock:
        if _cache and _cache[0] == stamp:
            return _cache[1]
        dataset = _load()
        _cache = (stamp, dataset)
        logger.info(
            "SkillSync dataset loaded: %d resumes, %d postings, %d skills (v%s)",
            len(dataset.resumes), len(dataset.jobs), len(dataset.skills), dataset.version,
        )
        return dataset


def get_resume(resume_id: str) -> Dict[str, Any]:
    resume = get_dataset().resumes.get(resume_id)
    if not resume:
        raise NotFound(
            "We couldn't find that resume.",
            hint="Choose a sample resume or upload yours again.",
        )
    return resume


def get_job(job_id: str) -> Dict[str, Any]:
    job = get_dataset().jobs.get(job_id)
    if not job:
        raise NotFound("We couldn't find that job.", hint="Go back to Job Matches and pick another role.")
    return job
