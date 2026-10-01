"""Export the SkillSync demo data as static JSON, for the GitHub Pages build.

    python backend/scripts/export_static.py frontend/dist/demo

GitHub Pages can only serve files, so the online demo cannot call the Python
backend. This script runs the same deterministic engine ahead of time for the
10 sample resumes and writes every result the dashboard needs:

    demo/index.json         resume list + job list
    demo/<resume-id>.json   profile, dashboard, matches, analysis, gaps,
                            improvements and every job-detail view

Only the sample data in /data is exported. Anything uploaded locally
(data/storage/uploads) is deliberately ignored, so private resumes and job
descriptions can never end up on a public site.
"""

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.skillsync import dataset  # noqa: E402

# Point the upload folders at an empty temp dir before anything is loaded.
_empty = Path(tempfile.mkdtemp())
dataset.uploads_dir = lambda: _empty
dataset.job_uploads_dir = lambda: _empty

from app.api.routes.skillsync import _resume_card  # noqa: E402
from app.skillsync import engine  # noqa: E402


def main(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    ds = dataset.get_dataset()
    resumes = [_resume_card(r) for r in ds.resumes.values()]
    roles = [{k: r[k] for k in ("role", "title", "summary", "core_skills", "posting_ids")} for r in ds.roles.values()]
    jobs = [engine.job_card(j) for j in ds.jobs.values()]
    (out / "index.json").write_text(json.dumps({
        "resumes": {"version": ds.version, "samples": resumes, "uploads": []},
        "jobs": {"roles": roles, "jobs": jobs},
    }, ensure_ascii=False))

    for rid, resume in ds.resumes.items():
        skills = {"": engine.gaps(rid)}
        for role in ds.roles:
            skills[f"role:{role}"] = engine.gaps(rid, role_id=role)
        for jid in ds.jobs:
            skills[f"job:{jid}"] = engine.gaps(rid, job_id=jid)
        bundle = {
            "resume": {**engine.profile(resume), "completion": engine.completion(resume)},
            "dashboard": engine.dashboard(rid),
            "matches": {"resume_id": rid, "matches": engine.matches(rid), "strong_threshold": engine.STRONG_MATCH},
            "analysis": engine.analysis(rid),
            "improvements": engine.improvements(rid),
            "skills": skills,
            "jobs": {jid: engine.job_detail(rid, jid) for jid in ds.jobs},
        }
        (out / f"{rid}.json").write_text(json.dumps(bundle, ensure_ascii=False))
    print(f"Exported {len(ds.resumes)} resumes and {len(ds.jobs)} jobs to {out}")


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "frontend/dist/demo"))
