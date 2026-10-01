"""Demo data.

Ships a realistic sample resume and three job descriptions so the whole
pipeline can be exercised in one click, without anyone uploading a real CV.
"""

from typing import Dict, List

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool

from app.api.deps import SessionDep, SettingsDep, StoreDep
from app.core.errors import AppError
from app.rag.ingest import ingest_text
from app.schemas.documents import LoadSampleRequest, SampleDocument
from app.utils.text import truncate

router = APIRouter(tags=["demo"])

SAMPLES: List[Dict[str, str]] = [
    {
        "id": "sample_resume",
        "file": "sample_resume.txt",
        "label": "Aarav Sharma - CS final year student",
        "doc_type": "resume",
        "description": (
            "A realistic student resume: Java, React, SQL and Git, three projects and "
            "one internship. No Docker, AWS or Kubernetes -- so the gap analysis has "
            "something real to find."
        ),
    },
    {
        "id": "jd_software_developer",
        "file": "jd_software_developer.txt",
        "label": "Software Developer (Backend)",
        "doc_type": "jd",
        "description": "Java, Spring Boot, REST, SQL, Docker, AWS. The closest match to the sample resume.",
    },
    {
        "id": "jd_data_analyst",
        "file": "jd_data_analyst.txt",
        "label": "Data Analyst",
        "doc_type": "jd",
        "description": "SQL, Python, Power BI, statistics. A deliberate partial match -- good for seeing a low score explained.",
    },
    {
        "id": "jd_frontend_developer",
        "file": "jd_frontend_developer.txt",
        "label": "Frontend Developer",
        "doc_type": "jd",
        "description": "React, TypeScript, CSS, accessibility. Strong on React, weak on TypeScript.",
    },
]

_BY_ID = {sample["id"]: sample for sample in SAMPLES}


def _read_sample(sample_id: str, settings) -> str:
    sample = _BY_ID.get(sample_id)
    if not sample:
        raise AppError(
            f"There's no sample document called '{sample_id}'.",
            hint="Call GET /api/samples to see what's available.",
            code="sample_not_found",
            status_code=404,
        )
    path = settings.documents_dir / sample["file"]
    if not path.exists():
        raise AppError(
            f"The sample file '{sample['file']}' is missing from data/documents/.",
            hint="Re-clone the repository or restore the data/documents folder.",
            code="sample_file_missing",
            status_code=500,
        )
    return path.read_text(encoding="utf-8")


@router.get("/samples", response_model=List[SampleDocument])
def list_samples(settings: SettingsDep) -> List[SampleDocument]:
    result = []
    for sample in SAMPLES:
        path = settings.documents_dir / sample["file"]
        preview = truncate(path.read_text(encoding="utf-8"), 320) if path.exists() else ""
        result.append(
            SampleDocument(
                id=sample["id"],
                label=sample["label"],
                doc_type=sample["doc_type"],
                description=sample["description"],
                preview=preview,
            )
        )
    return result


@router.post("/sessions/{session_id}/samples/load")
async def load_samples(
    session_id: SessionDep,
    payload: LoadSampleRequest,
    settings: SettingsDep,
    store: StoreDep,
):
    """Ingest one or both sample documents into this session."""
    loaded = []

    for sample_id, doc_type in ((payload.resume_id, "resume"), (payload.jd_id, "jd")):
        if not sample_id:
            continue
        text = _read_sample(sample_id, settings)
        sample = _BY_ID[sample_id]
        result = await run_in_threadpool(
            ingest_text,
            text,
            session_id=session_id,
            doc_type=doc_type,
            settings=settings,
            store=store,
            doc_name=sample["label"],
        )
        loaded.append(
            {
                "doc_type": doc_type,
                "doc_name": result.doc_name,
                "chunk_count": result.chunk_count,
                "sections": result.sections,
                "pipeline": result.pipeline_trace(),
            }
        )

    if not loaded:
        raise AppError(
            "No sample was selected.",
            hint="Pass resume_id and/or jd_id.",
            code="no_sample_selected",
            status_code=400,
        )

    return {"loaded": loaded, "session_id": session_id}
