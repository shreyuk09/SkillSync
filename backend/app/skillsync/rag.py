"""SkillSync RAG: knowledge-base index, per-resume index, retrieval and chat.

Pipeline
    documents (jobs, roles, skills, resume, analysis, gaps, improvements)
      -> chunks (one idea per chunk, each with a citation label)
      -> embeddings (the same all-MiniLM-L6-v2 model the rest of the app uses)
      -> vector index (NumPy matrix, saved to data/storage/skillsync/*.npz)
      -> semantic retrieval (cosine + small, explainable boosts)
      -> LLM answer that may only use the retrieved sources, with citations

Indexes are content-addressed: the knowledge base file is named after a hash
of the jobs + skills data, and each resume index after the resume's hash. They
are built once, loaded from disk after a restart, and rebuilt only when the
underlying JSON changes.
"""

import json
import re
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from app.core.config import get_settings
from app.core.logging import get_logger
from app.rag.embeddings import get_embedder
from app.skillsync import engine
from app.skillsync import skills as sk
from app.skillsync.dataset import get_dataset, get_job, get_resume

logger = get_logger(__name__)

REFUSAL = "I don't have enough information in the current SkillSync knowledge base to answer that."
MIN_RELEVANCE = 0.22
TOP_K = 6


@dataclass
class Chunk:
    id: str
    kind: str  # resume | job | role | skill | analysis | gaps | improvement | match
    ref: str  # resume id / job id / skill name
    label: str  # shown to the user, e.g. "Job: java-developer-01"
    title: str
    text: str
    url: Optional[str] = None


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------
def kb_chunks() -> List[Chunk]:
    ds = get_dataset()
    out: List[Chunk] = []
    for role in ds.roles.values():
        out.append(Chunk(f"role:{role['role']}", "role", role["role"], f"Role: {role['title']}", role["title"],
                         f"{role['title']} role overview. {role['summary']} Core skills: {', '.join(role['core_skills'])}."))
    for job in ds.jobs.values():
        if not job.get("uploaded"):
            out.extend(job_chunks(job))
    for skill in ds.skills.values():
        out.append(Chunk(f"skill:{skill['name']}", "skill", skill["name"], f"Skill Knowledge: {skill['name']}", skill["name"],
                         f"{skill['name']} ({skill['category']}): {skill['description']} How to learn or show it: {skill['how_to_learn']}"))
    return out


def job_chunks(job: Dict[str, Any]) -> List[Chunk]:
    uploaded = bool(job.get("uploaded"))
    head = (f"{job['title']} at {job['company']} ({job['id']}). {job['location']}, {job['work_type']}, "
            f"{job['level']}, experience: {job['experience']}. Role family: {job['role_title']}.")
    label = f"Your JD: {job['title']}" if uploaded else f"Job: {job['id']}"
    common = dict(kind="job", ref=job["id"], label=label, title=f"{job['title']} · {job['company']}", url=job.get("source_url"))
    origin = ("This is a job description the user uploaded." if uploaded
              else f"Source: {job['source_name']}, retrieved {job['retrieved_at']}; the role may no longer be open.")
    out = [
        Chunk(f"job:{job['id']}:overview", text=(
            f"{head} Summary: {job['summary']} Required skills: {', '.join(job['required_skills'])}. "
            f"Preferred skills: {', '.join(job['preferred_skills']) or 'none listed'}. {origin}"), **common),
        Chunk(f"job:{job['id']}:work", text=(
            f"{job['title']} at {job['company']} — responsibilities: " + "; ".join(job.get("responsibilities", []))
            + ". Requirements: " + "; ".join(job.get("requirements", [])) + "."), **common),
    ]
    # The user's own document: index its full text too, in paragraph-sized pieces.
    piece, n = "", 0
    for para in (job.get("full_text") or "").split("\n"):
        piece = f"{piece}\n{para}".strip()
        if len(piece) > 700:
            out.append(Chunk(f"job:{job['id']}:text{n}", text=f"From the uploaded job description ({job['title']}): {piece}", **common))
            piece, n = "", n + 1
    if piece and n < 40:
        out.append(Chunk(f"job:{job['id']}:text{n}", text=f"From the uploaded job description ({job['title']}): {piece}", **common))
    return out


def resume_chunks(resume_id: str) -> List[Chunk]:
    r = get_resume(resume_id)
    label = f"Resume: {resume_id}"
    out: List[Chunk] = []

    def add(suffix: str, title: str, text: str, kind: str = "resume", lab: str = label, ref: str = resume_id):
        out.append(Chunk(f"{resume_id}:{suffix}", kind, ref, lab, title, text))

    add("profile", "Profile", f"Candidate {r.get('name')} — {r.get('headline')}, {r.get('location')}. "
        f"{engine.years_of(r):g} years of experience. Summary: {r.get('summary') or 'no summary written'}")
    for i, job in enumerate(r.get("experience", [])):
        add(f"exp{i}", f"Experience · {job.get('company')}", f"Experience: {job.get('title')} at {job.get('company')} "
            f"({job.get('start')} – {job.get('end')}). " + " ".join(f"- {b}" for b in job.get("bullets", [])))
    for i, p in enumerate(r.get("projects", [])):
        add(f"proj{i}", f"Project · {p.get('name')}", f"Project: {p.get('name')} using {', '.join(p.get('tech', []))}. {p.get('description', '')}")
    s = r.get("skills", {})
    add("skills", "Skills", f"Technical skills listed: {', '.join(s.get('technical', []))}. Soft skills: {', '.join(s.get('soft', []))}.")
    edu = "; ".join(f"{e.get('degree')}, {e.get('institution')} ({e.get('start')}–{e.get('end')})"
                    + (f", {e['grade']}" if e.get("grade") else "") for e in r.get("education", []))
    add("education", "Education & certifications", f"Education: {edu or 'none listed'}. Certifications: "
        f"{', '.join(r.get('certifications', [])) or 'none'}. Achievements: {', '.join(r.get('achievements', [])) or 'none'}.")

    a = engine.analysis(resume_id)
    add("analysis", "Resume analysis", f"Resume analysis for {resume_id}: overall score {a['overall']}/100 ({a['grade']}), "
        f"target role {a['target_role_title']}. " + "; ".join(f"{x['label']} {x['value']}" for x in a["scores"])
        + ". Working well: " + " ".join(a["whats_working"]) + " Needs improvement: " + " ".join(a["needs_improvement"]),
        kind="analysis", lab=f"Resume Analysis: {resume_id}")

    g = engine.gaps(resume_id)
    by = {k: [x["skill"] for x in g["skills"] if x["status"] == k] for k in ("strong", "improve", "missing")}
    add("gaps", "Skill gaps", f"Skill gap analysis of {resume_id} against {g['target']['title']} roles. "
        f"STRONG (shown in work or projects): {', '.join(by['strong']) or 'none'}. "
        f"NEEDS IMPROVEMENT (listed without evidence, or only a related skill — not missing): {', '.join(by['improve']) or 'none'}. "
        f"MISSING (not in the resume at all): {', '.join(by['missing']) or 'none'}. Suggested next skills to learn: "
        + "; ".join([f"{x['skill']} — {x['recommendation']}" for x in g["skills"] if x["status"] == "missing"][:4]),
        kind="gaps", lab=f"Skill Gaps: {resume_id}")

    ms = engine.matches(resume_id)
    add("matches", "Job matches", f"Best job matches for {resume_id}: " + "; ".join(
        f"{m['title']} at {m['company']} ({m['id']}) {m['match']}% {m['label']}" for m in ms[:6]) + ".",
        kind="match", lab=f"Job Matches: {resume_id}")
    for m in ms:
        add(f"match:{m['id']}", f"Match · {m['title']}", f"Why {resume_id} matches {m['title']} at {m['company']} ({m['id']}): "
            f"{m['match']}% ({m['label']}). {m['explanation']} Matched skills: {', '.join(m['matched_skills']) or 'none'}. "
            f"Missing skills: {', '.join(m['missing_skills']) or 'none'}.", kind="match", lab=f"Job: {m['id']}", ref=m["id"])

    for item in engine.improvements(resume_id)["items"]:
        add(f"imp:{item['id']}", f"Improvement · {item['title']}", f"Improvement ({item['category']}, {item['priority']} priority): "
            f"{item['title']}. Problem: {item['problem']} Why it matters: {item['why']} Action: {item['action']}",
            kind="improvement", lab=f"Improvements: {resume_id}")
    return out


# ---------------------------------------------------------------------------
# Index (build once, persist, reload)
# ---------------------------------------------------------------------------
class Index:
    def __init__(self, chunks: List[Chunk], vectors: np.ndarray) -> None:
        self.chunks = chunks
        self.vectors = vectors


_indexes: "OrderedDict[str, Index]" = OrderedDict()
_lock = threading.Lock()
_ready = threading.Event()


def _dir() -> Path:
    path = get_settings().storage_dir / "skillsync"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _embedder():
    return get_embedder(get_settings())


_building: Dict[str, threading.Lock] = {}


def _build(key: str, make_chunks) -> Index:
    with _lock:
        if key in _indexes:
            _indexes.move_to_end(key)
            return _indexes[key]
        build_lock = _building.setdefault(key, threading.Lock())
    # One builder per index: a second request for the same key waits and
    # then reuses the result instead of embedding (and writing) it twice.
    with build_lock:
        with _lock:
            if key in _indexes:
                return _indexes[key]
        index = _load_or_embed(key, make_chunks)
        with _lock:
            _indexes[key] = index
            _building.pop(key, None)
            while len(_indexes) > 24:
                _indexes.popitem(last=False)
        return index


def _load_or_embed(key: str, make_chunks) -> Index:
    emb = _embedder()
    path = _dir() / f"{key}-{emb.name}.npz"
    index: Optional[Index] = None
    if path.exists():
        try:
            data = np.load(path, allow_pickle=False)
            chunks = [Chunk(**c) for c in json.loads(str(data["meta"]))]
            index = Index(chunks, data["vectors"])
        except Exception as exc:
            logger.warning("Rebuilding unreadable index %s (%s)", path.name, exc)
    if index is None:
        started = time.perf_counter()
        chunks = make_chunks()
        vectors = emb.embed_documents([f"{c.title}. {c.text}" for c in chunks])
        index = Index(chunks, vectors)
        tmp = path.with_name(f"{path.stem}.{threading.get_ident()}.tmp.npz")
        np.savez(tmp, vectors=vectors, meta=np.array(json.dumps([c.__dict__ for c in chunks])))
        tmp.replace(path)
        logger.info("Indexed %s: %d chunks in %.1fs", key, len(chunks), time.perf_counter() - started)
    return index


def kb_index() -> Index:
    return _build(f"kb-{get_dataset().kb_version}", kb_chunks)


def resume_index(resume_id: str) -> Index:
    ds = get_dataset()
    get_resume(resume_id)
    return _build(f"resume-{resume_id}-{ds.resume_hashes[resume_id]}-{ds.jobs_version}", lambda: resume_chunks(resume_id))


def uploads_index() -> Optional[Index]:
    """Uploaded job descriptions live in their own small index, so adding one
    never re-embeds the shared knowledge base."""
    ds = get_dataset()
    if not ds.uploaded_jobs:
        return None
    return _build(f"ujobs-{ds.jobs_version}", lambda: [c for j in ds.uploaded_jobs for c in job_chunks(ds.jobs[j])])


def warmup() -> None:
    """Load the model and indexes in the background so the first chat is fast."""
    def run():
        try:
            started = time.perf_counter()
            kb_index()
            uploads_index()
            for rid in list(get_dataset().resumes):
                resume_index(rid)
            logger.info("SkillSync RAG ready in %.1fs", time.perf_counter() - started)
        except Exception:
            logger.exception("SkillSync warmup failed (chat will build indexes on demand)")
        finally:
            _ready.set()
    threading.Thread(target=run, name="skillsync-warmup", daemon=True).start()


def is_ready() -> bool:
    return _ready.is_set()


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------
_INTENTS = [
    (re.compile(r"\b(miss|gap|lack|learn|next|study)", re.I), ("gaps", "skill")),
    (re.compile(r"\b(improv|better|fix|stronger|rewrite|add)", re.I), ("improvement", "analysis")),
    (re.compile(r"\b(match|jobs?|roles?|fit|apply|suit)", re.I), ("match",)),
    (re.compile(r"\b(score|ats|analy)", re.I), ("analysis",)),
    (re.compile(r"\bprojects?\b", re.I), ("improvement", "resume")),
]
# Questions that compare across jobs need other postings even when one job is in focus.
_ACROSS_JOBS = re.compile(r"\b(other|compare|comparison|which (job|role)s?|best|top|all (the )?(jobs|roles)|more jobs|similar)\b", re.I)


def _tokens(text: str) -> List[str]:
    return re.findall(r"[a-z0-9+#.]+", text.lower())


def _bm25(query: str, docs: List[str]) -> np.ndarray:
    """Lexical relevance (BM25). Embeddings miss exact terms like 'Kafka' or
    'CGPA' surprisingly often; combining both is standard hybrid retrieval."""
    q = [t for t in set(_tokens(query)) if len(t) > 2]
    if not q:
        return np.zeros(len(docs), dtype=np.float32)
    toks = [_tokens(d) for d in docs]
    avg = sum(len(t) for t in toks) / max(1, len(toks))
    n = len(docs)
    out = np.zeros(n, dtype=np.float32)
    for term in q:
        df = sum(1 for t in toks if term in t)
        if not df:
            continue
        idf = np.log(1 + (n - df + 0.5) / (df + 0.5))
        for i, t in enumerate(toks):
            tf = t.count(term)
            if tf:
                out[i] += idf * tf * 2.2 / (tf + 1.2 * (0.25 + 0.75 * len(t) / avg))
    return out / out.max() if out.max() > 0 else out


def retrieve(question: str, resume_id: str, job_id: Optional[str] = None, k: int = TOP_K,
             exclude: Optional[set] = None) -> List[Dict[str, Any]]:
    parts = [ix for ix in (kb_index(), uploads_index(), resume_index(resume_id)) if ix is not None]
    chunks = [c for ix in parts for c in ix.chunks]
    matrix = np.vstack([ix.vectors for ix in parts])
    q = _embedder().embed_query(question)
    scores = matrix @ q
    lexical = _bm25(question, [f"{c.title} {c.text}" for c in chunks])

    boost = np.zeros(len(chunks), dtype=np.float32)
    kinds = set()
    for pattern, ks in _INTENTS:
        if pattern.search(question):
            kinds.update(ks)
    named = set(sk.find_in_text(question))
    target_role = engine.target_role(resume_id)
    gap_skills = {x["skill"] for x in engine.gaps(resume_id)["skills"] if x["status"] != "strong"}
    top_jobs = {m["id"] for m in engine.matches(resume_id)[:6]}
    across = bool(_ACROSS_JOBS.search(question))
    for i, c in enumerate(chunks):
        if c.kind in kinds:
            boost[i] += 0.08
        if job_id and c.ref == job_id:
            boost[i] += 0.15
        if job_id and not across and c.kind in ("job", "match", "role") and c.ref != job_id:
            boost[i] -= 0.2  # a focused question is about THAT job, not others
        if c.kind == "skill":
            # Skill knowledge is useful when it is about this candidate's gaps
            # or the skill the user named -- not generic soft-skill blurbs.
            boost[i] += 0.12 if c.ref in named else 0.04 if c.ref in gap_skills else -0.12
            if c.ref not in named and sk.info(c.ref).get("category") == "Soft skills":
                boost[i] -= 0.08
        if c.kind == "match" and c.ref not in top_jobs and c.ref != job_id:
            boost[i] -= 0.06
        if c.kind == "job" and not job_id and not c.ref.startswith(target_role) and not c.ref.startswith("jd-"):
            boost[i] -= 0.04  # prefer postings in the candidate's own field
    final = 0.75 * scores + 0.25 * lexical + boost

    picked: List[int] = []
    seen_jobs: Dict[str, int] = {}
    for i in np.argsort(-final):
        c = chunks[i]
        if exclude and c.id in exclude:
            continue
        if c.kind == "job":  # at most 2 chunks per posting, keep variety
            if seen_jobs.get(c.ref, 0) >= (3 if c.ref == job_id else 2):
                continue
            seen_jobs[c.ref] = seen_jobs.get(c.ref, 0) + 1
        picked.append(int(i))
        if len(picked) >= k:
            break
    return [{
        "id": chunks[i].id, "kind": chunks[i].kind, "ref": chunks[i].ref, "label": chunks[i].label,
        "title": chunks[i].title, "text": chunks[i].text, "url": chunks[i].url,
        "similarity": round(float(scores[i]), 3), "score": round(float(final[i]), 3),
    } for i in picked]


# ---------------------------------------------------------------------------
# Core context: the whole resume, the whole job, and the computed match facts
# ---------------------------------------------------------------------------
def resume_document(resume_id: str) -> str:
    """The complete resume as text. Resumes are short, so the model always sees
    all of it -- a question like "where have I worked?" must never depend on
    whether one experience chunk happened to rank in the top k."""
    r = get_resume(resume_id)
    out = [f"Name: {r.get('name')}", f"Headline: {r.get('headline')}"]
    if r.get("location"):
        out.append(f"Location: {r['location']}")
    out.append(f"Total experience: {engine.years_of(r):g} years")
    if r.get("summary"):
        out.append(f"Summary: {r['summary']}")
    for j in r.get("experience", []):
        out.append(f"Experience: {j.get('title')} at {j.get('company')} ({j.get('start')} – {j.get('end')})"
                   + "".join(f"\n  - {b}" for b in j.get("bullets", [])))
    for p in r.get("projects", []):
        out.append(f"Project: {p.get('name')} [{', '.join(p.get('tech', []))}] — {p.get('description', '')}")
    for e in r.get("education", []):
        out.append(f"Education: {e.get('degree')}, {e.get('institution')}"
                   + (f" ({e.get('start')}–{e.get('end')})" if e.get("end") else "")
                   + (f", grade {e['grade']}" if e.get("grade") else "")
                   + (f", coursework: {', '.join(e['coursework'])}" if e.get("coursework") else ""))
    sk_ = r.get("skills", {})
    out.append(f"Technical skills listed: {', '.join(sk_.get('technical', [])) or 'none'}")
    out.append(f"Soft skills listed: {', '.join(sk_.get('soft', [])) or 'none'}")
    out.append(f"Certifications: {', '.join(r.get('certifications', [])) or 'none'}")
    out.append(f"Achievements: {', '.join(r.get('achievements', [])) or 'none'}")
    if r.get("interests"):
        out.append(f"Interests: {', '.join(r['interests'])}")
    return "\n".join(out)


def job_document(job: Dict[str, Any]) -> str:
    out = [f"Job title: {job['title']}", f"Company: {job['company']}", f"Location: {job['location']} ({job['work_type']})",
           f"Level: {job['level']}; experience asked: {job['experience']}"]
    for k, v in (job.get("details") or {}).items():
        out.append(f"{k.capitalize()}: {v}")
    out.append(f"Summary: {job['summary']}")
    out.append(f"Required skills: {', '.join(job['required_skills']) or 'none listed'}")
    out.append(f"Preferred / nice-to-have skills: {', '.join(job['preferred_skills']) or 'none listed'}")
    if job.get("responsibilities"):
        out.append("Responsibilities:" + "".join(f"\n  - {x}" for x in job["responsibilities"]))
    if job.get("requirements"):
        out.append("Requirements:" + "".join(f"\n  - {x}" for x in job["requirements"]))
    if job.get("uploaded"):
        out.append("Origin: uploaded by the user.")
    else:
        out.append(f"Origin: summary of a public listing on {job['source_name']}, captured {job['retrieved_at']}; it may no longer be open.")
    return "\n".join(out)


def match_document(resume_id: str, job_id: str) -> str:
    d = engine.job_detail(resume_id, job_id)
    have = [f"{h['skill']}" + (f" (via {h['via']})" if h.get("via") else "")
            + (f" — evidence: \"{h['evidence'][0]['text']}\" ({h['evidence'][0]['where']})" if h["evidence"] else " — listed, no evidence in work/projects")
            for h in d["skills_you_have"]]
    return "\n".join([
        f"Match score: {d['match']}% ({d['label']}). Breakdown: required skills {d['breakdown']['required_skills']}%, "
        f"preferred {d['breakdown']['preferred_skills']}%, role focus {d['breakdown']['role_fit']}%, experience {d['breakdown']['experience_fit']}%.",
        "Skills the resume HAS for this job:" + "".join(f"\n  - {h}" for h in have) if have else "Skills the resume HAS for this job: none",
        "PARTIAL (only a related skill): " + (", ".join(f"{p['skill']} (related: {p['related']})" for p in d["skills_partial"]) or "none"),
        "MISSING required skills: " + (", ".join(s["skill"] for s in d["skills_missing"] if s["required"]) or "none"),
        "MISSING nice-to-have skills: " + (", ".join(s["skill"] for s in d["skills_missing"] if not s["required"]) or "none"),
        "Why: " + " ".join(d["why_you_match"]),
        "Most valuable to add: " + ("; ".join(f"{b['skill']} (+{b['gain']} points)" for b in d["recommended_improvements"]) or "nothing"),
    ])


_THIS_JOB = re.compile(r"\b(this|that|the|my) (job|role|position|posting|vacancy|jd|job description)\b|\bjd\b|job description", re.I)


def infer_job(question: str, resume_id: str, job_id: Optional[str]) -> Optional[str]:
    """Which job is the question about? Explicit selection wins; then a job
    named in the question; then "this job" -> the latest uploaded JD, or the
    best match if none was uploaded."""
    if job_id:
        return job_id
    ds = get_dataset()
    q = question.lower()
    for jid, job in ds.jobs.items():
        company = job["company"].lower()
        if (len(company) > 3 and company in q and company != "your job description") or job["title"].lower() in q:
            return jid
    if _THIS_JOB.search(question):
        if ds.uploaded_jobs:
            return max(ds.uploaded_jobs, key=lambda j: (ds.jobs[j].get("retrieved_at", ""), j))
        top = engine.matches(resume_id)
        return top[0]["id"] if top else None
    return None


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------
_SYSTEM = f"""You are SkillSync's AI Career Assistant. You answer one candidate's questions about THEIR resume and THEIR job descriptions.

Grounding rules (most important):
- Use ONLY the numbered sources. Every fact you state must come from them. Do not use outside knowledge about companies, salaries, tools or the candidate.
- Cite after each claim with the source number in square brackets, e.g. [S1] or [S2][S3]. Use the exact form [S1].
- Treat "Resume" sources as the only truth about the candidate and "Job" sources as the only truth about the job. Never move facts between them.
- For which skills the candidate has or is missing for a job, use the "Match facts" source exactly as written. Do not recompute it, and do not call a PARTIAL skill missing or a MISSING skill present.
- When asked to list things (projects, jobs, skills, certifications), list ALL of them from the source, not just some.
- Quote numbers, dates, grades, titles and names exactly as written.
- When the job states conditions or exceptions (e.g. what counts as experience, "or equivalent", "desirable"), include them.
- If asked whether the candidate has a skill or experience that the resume does not mention, say plainly that their resume doesn't mention it (that is an answer, not a refusal), and cite the resume.
- If the sources do not contain the answer at all, reply with exactly: "{REFUSAL}" followed by one short sentence saying what information would be needed.
- Job postings from the SkillSync dataset are summaries captured on a past date: never say a company is currently hiring.

Style: plain English, at most ~150 words, short bullets for lists, no headings, address the candidate as "you"."""

_answers: "OrderedDict[Tuple, Dict[str, Any]]" = OrderedDict()
_PERSONAL = re.compile(r"\b(i|i'm|im|my|me|mine|myself|am i|do i|have i|this job|the job|jd|job description|resume|cv)\b", re.I)


def _normalise_citations(text: str, n: int) -> str:
    text = re.sub(r"[​-‍﻿]", "", text)
    text = re.sub(r"[【\[]\s*(S\d+)\s*[】\]]", r"[\1]", text)
    # "[4]" or "[4][5]" -> "[S4]" when 4 is a real source number
    text = re.sub(r"\[(\d{1,2})\]", lambda m: f"[S{m.group(1)}]" if 1 <= int(m.group(1)) <= n else m.group(0), text)
    text = re.sub(r"\[S(\d+)\s*,\s*S?(\d+)\]", r"[S\1][S\2]", text)
    return text


def _cite_parse(text: str, n: int) -> List[int]:
    found = []
    for m in re.finditer(r"\[S(\d+)\]", text):
        i = int(m.group(1))
        if 1 <= i <= n and i not in found:
            found.append(i)
    return found


def _unsupported_skills(answer: str, sources: List[Dict[str, Any]], question: str) -> List[str]:
    """Skills named in the answer that appear in no source: a hallucination signal."""
    src = " ".join(s["text"] for s in sources).lower() + " " + question.lower()
    bad = []
    for name in sk.find_in_text(answer):
        terms = [name] + sk.info(name).get("aliases", [])
        if not any(t.lower() in src for t in terms):
            bad.append(name)
    return bad


def _source(ref_id: str, kind: str, ref: str, label: str, title: str, text: str, url: Optional[str] = None) -> Dict[str, Any]:
    return {"id": f"core:{kind}:{ref}", "kind": kind, "ref": ref, "label": label, "title": title, "text": text,
            "url": url, "similarity": 1.0, "score": 1.0, "ref_id": ref_id, "core": True}


def build_context(question: str, resume_id: str, job_id: Optional[str], retrieval_query: str) -> List[Dict[str, Any]]:
    r = get_resume(resume_id)
    core = [_source("", "resume", resume_id, f"Resume: {r.get('name') or resume_id}", "Full resume", resume_document(resume_id))]
    exclude = {f"{resume_id}:{s}" for s in ("profile", "skills", "education")}
    exclude |= {c.id for c in resume_index(resume_id).chunks if c.id.startswith((f"{resume_id}:exp", f"{resume_id}:proj"))}
    if job_id:
        job = get_job(job_id)
        jl = f"Your JD: {job['title']}" if job.get("uploaded") else f"Job: {job_id}"
        core.append(_source("", "job", job_id, jl, f"{job['title']} · {job['company']}", job_document(job), job.get("source_url")))
        core.append(_source("", "match", job_id, f"Match facts: {job['title']}", "Your resume vs this job", match_document(resume_id, job_id)))
        exclude |= {f"job:{job_id}:overview", f"job:{job_id}:work", f"{resume_id}:match:{job_id}"}
    extra = retrieve(retrieval_query, resume_id, job_id, k=TOP_K - 1 if job_id else TOP_K, exclude=exclude)
    sources = core + extra
    for i, s in enumerate(sources, 1):
        s["ref_id"] = f"S{i}"
    return sources


def chat(question: str, resume_id: str, job_id: Optional[str] = None, history: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
    question = (question or "").strip()[:600]
    ds = get_dataset()
    if job_id:
        get_job(job_id)
    started = time.perf_counter()
    cache_key = (resume_id, ds.resume_hashes.get(resume_id), ds.jobs_version, job_id, question.lower(), tuple(
        (h.get("role"), h.get("content")) for h in (history or [])[-4:]))
    if cache_key in _answers:
        return {**_answers[cache_key], "cached": True}

    retrieval_query = question
    if history:  # follow-ups ("what about the second one?") need the previous turn
        last_user = next((h["content"] for h in reversed(history) if h.get("role") == "user"), "")
        if last_user and len(question.split()) < 8:
            retrieval_query = f"{last_user} {question}"
    focus = infer_job(retrieval_query, resume_id, job_id)
    sources = build_context(question, resume_id, focus, retrieval_query)
    base = {"question": question, "resume_id": resume_id, "job_id": focus, "retrieval_ms": round((time.perf_counter() - started) * 1000)}

    retrieved = [s for s in sources if not s.get("core")]
    personal = bool(_PERSONAL.search(question)) or bool(focus)
    if not personal and (not retrieved or max(s["similarity"] for s in retrieved) < MIN_RELEVANCE):
        return {**base, "answer": f"{REFUSAL} Try asking about your resume, your skills, or one of the job matches — or upload a resume that includes the details you're asking about.",
                "grounded": False, "mode": "refused", "sources": sources[:3], "used_sources": []}

    context = "\n\n".join(f"[{s['ref_id']}] {s['label']} — {s['title']}\n{s['text']}" for s in sources)
    lead = ""
    if focus:
        job = get_job(focus)
        lead = f"The question is about the job \"{job['title']}\" at {job['company']}.\n"
    messages = []
    for h in (history or [])[-4:]:
        if h.get("role") in ("user", "assistant") and h.get("content"):
            messages.append({"role": h["role"], "content": h["content"][:800]})
    messages.append({"role": "user", "content": f"{lead}Sources:\n{context}\n\nQuestion: {question}"})

    from app.core.errors import AppError
    from app.rag.llm import get_llm
    llm = get_llm(get_settings())
    try:
        answer = llm.complete(system=_SYSTEM, messages=messages, max_tokens=900, effort="low")
        answer = _normalise_citations(answer.strip(), len(sources))
        # Verification pass: if the answer names a skill no source mentions,
        # ask once more with that pointed out. Cheap, and it catches the most
        # common kind of slip ("you also know Docker").
        bad = _unsupported_skills(answer, sources, question)
        if bad and not answer.startswith(REFUSAL[:40]):
            logger.info("Answer named unsupported skills %s; regenerating.", bad)
            retry = messages + [{"role": "assistant", "content": answer},
                                {"role": "user", "content": f"Your answer mentions {', '.join(bad)}, which appear in none of the sources. Rewrite the answer using only facts in the sources, with citations."}]
            answer = _normalise_citations(llm.complete(system=_SYSTEM, messages=retry, max_tokens=900, effort="low").strip(), len(sources))
    except AppError as exc:
        logger.info("Chat LLM unavailable: %s", exc.message)
        return {**base, "answer": None, "mode": "retrieval_only", "grounded": True,
                "notice": f"The AI model isn't available right now ({exc.message}) Here is the most relevant information SkillSync found.",
                "sources": sources, "used_sources": [s["ref_id"] for s in sources[:3]]}

    answer = answer or REFUSAL
    used = _cite_parse(answer, len(sources))
    refused = answer.startswith(REFUSAL[:40])
    result = {**base, "answer": answer, "mode": "refused" if refused else "answer", "grounded": True,
              "sources": sources, "used_sources": [f"S{i}" for i in used] or ([] if refused else [s["ref_id"] for s in sources[:2]]),
              "total_ms": round((time.perf_counter() - started) * 1000)}
    _answers[cache_key] = result
    while len(_answers) > 200:
        _answers.popitem(last=False)
    return result
