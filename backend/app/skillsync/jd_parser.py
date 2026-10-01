"""Turn an uploaded job description (PDF, DOCX, TXT, image or pasted text)
into the same shape as the sample postings, so it can be matched, compared
and discussed with the assistant like any other job.

Deterministic: headings split the text into sections, the skill dictionary
finds skills, and a few patterns pick out title, company, location, years.
The user's own full text is kept (locally) so the assistant can quote it.
"""

import hashlib
import json
import re
from datetime import date
from typing import Any, Dict, List, Optional

from app.core.errors import AppError
from app.rag.extraction import extract_document, extract_from_plain_text
from app.skillsync import skills as sk
from app.skillsync.dataset import get_dataset, job_uploads_dir

_SECTIONS = {
    "about": r"about (the )?(company|us|team|role|job|position)|overview|job summary|summary|the role|role overview|who we are",
    "responsibilities": r"job purpose|main (duties|responsibilities)|key duties|(key )?responsibilities|what you('| wi)ll do|what you will be doing|your (role|impact|day[- ]to[- ]day)|duties|in this role.*|the job|job description",
    "requirements": r"essential( criteria| requirements| skills)?|shortlisting criteria|person specification|selection criteria|key skills|requirements|(minimum |basic |required )?qualifications|what you('| wi)ll need|what we('re| are) looking for|must[- ]haves?|who you are|skills( required| & experience| and experience)?|you have|about you|experience",
    "preferred": r"desirable( criteria| requirements| skills)?|preferred( qualifications| skills)?|nice[- ]to[- ]haves?|bonus( points)?|pluses|good to have|desired|additional (skills|qualifications)|it'?s a plus",
    "benefits": r"benefits|perks|what we offer|compensation|why (join|work)( with)? us|equal opportunity.*",
}
_HEAD = {k: re.compile(rf"^\s*(?:#+\s*)?({v})\s*[:：]?\s*$", re.I) for k, v in _SECTIONS.items()}
_BULLET = re.compile(r"^\s*(?:[-•*▪●◦·–]|\d+[.)])\s*")
_FIELD = re.compile(r"^\s*(job title|title|position|role|company|organi[sz]ation|employer|location|job location|work type|workplace|employment type|salary|salary range|pay|compensation|grade|contract|hours|closing date)\s*[:：-]\s*(.+)$", re.I)
# Strong organisation endings first ("Northern Ireland Assembly"), then weaker
# ones that are often a department ("Parliamentary Services").
_ORG_SUFFIXES = [
    r"(?:Assembly|Council|Ltd\.?|Limited|Inc\.?|LLC|plc|PLC|University|College|Bank|Corporation|Corp\.?|Trust|Hospital|Foundation|Authority|Ministry|Agency|Group)",
    r"(?:Technologies|Solutions|Systems|Labs|Software|Services|Service|Department)",
]
_RESUME_HEADS = re.compile(r"^\s*(education|projects?|professional summary|career objective|objective|certifications?|achievements|internships?|work experience|technical skills|personal details|declaration|hobbies)\s*:?\s*$", re.I | re.M)
_JD_WORDS = re.compile(r"\b(responsibilit|requirements?|qualifications?|you will|you'll|we are looking|we're looking|the successful candidate|applicants?|candidates? (will|should|must)|job purpose|duties|salary|benefits|apply)\b", re.I)
_YEARS = re.compile(r"(\d{1,2})\s*\+?\s*(?:(?:-|–|to)\s*(\d{1,2})\s*)?(?:\+\s*)?years?", re.I)


class NotAJobDescription(AppError):
    code = "not_a_job_description"
    status_code = 422


def _sections(lines: List[str]) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {"header": []}
    current = "header"
    for line in lines:
        short = len(line) < 60
        for key, pattern in _HEAD.items():
            if short and pattern.match(line):
                current = key
                out.setdefault(key, [])
                break
        else:
            out.setdefault(current, []).append(line)
    return out


def _clean(line: str) -> str:
    return _BULLET.sub("", line).strip().rstrip(";")


def _level(title: str, years: Optional[int]) -> str:
    t = title.lower()
    if re.search(r"\b(intern|graduate|new grad|junior|jr\.?|entry|associate|trainee|fresher)\b", t):
        return "Entry level"
    if re.search(r"\b(senior|sr\.?|lead|staff|principal|head|manager|architect)\b", t):
        return "Senior"
    if years is None:
        return "Not specified"
    return "Entry level" if years <= 1 else "Mid level" if years <= 4 else "Senior"


def _best_role(required: List[str], text: str) -> str:
    """Which role family does this JD belong to? Most core-skill overlap wins;
    words in the title break ties."""
    ds = get_dataset()
    have = set(required)
    title = text[:200].lower()

    def score(role: Dict[str, Any]) -> float:
        core = role["core_skills"]
        overlap = sum(1 for s in core if sk.covered_by(s, have) or s in have) / max(1, len(core))
        words = [w for w in role["title"].lower().replace("/", " ").split() if len(w) > 2 and w != "developer"]
        return overlap + (0.5 if any(w in title for w in words) else 0)

    return max(ds.roles.values(), key=score)["role"]


def _looks_like_resume(text: str) -> bool:
    """A resume uploaded through the job-description button is an easy mistake;
    matching a resume against itself gives nonsense, so catch it."""
    head = text[:400]
    contact = bool(re.search(r"[\w.+-]+@[\w-]+\.\w+", head)) or bool(re.search(r"(\+?\d[\d\s-]{8,}\d)", head))
    resume_heads = len(set(m.lower() for m in _RESUME_HEADS.findall(text)))
    jd_words = len(_JD_WORDS.findall(text))
    return (contact and resume_heads >= 2 and jd_words <= 3) or (resume_heads >= 4 and jd_words <= 1)


def parse_job_description(text: str, source_label: str) -> Dict[str, Any]:
    if _looks_like_resume(text):
        raise NotAJobDescription(
            "This looks like a resume, not a job description.",
            hint="Upload resumes on the My Resume page. Here, upload the job posting you want to compare your resume with.",
        )
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    fields: Dict[str, str] = {}
    body: List[str] = []
    for line in lines:
        m = _FIELD.match(line)
        if m and len(m.group(2)) < 100 and m.group(1).lower() not in fields:
            fields[m.group(1).lower()] = m.group(2).strip()
        else:
            body.append(line)
    sec = _sections(body)

    title = fields.get("job title") or fields.get("title") or fields.get("position") or fields.get("role")
    if not title:
        title = next((l for l in sec.get("header", [])[:4] if 3 < len(l) < 80 and not l.endswith(".")), None) or "Uploaded job description"
    company = fields.get("company") or fields.get("organization") or fields.get("organisation") or fields.get("employer")
    if not company:
        at = re.search(r"\b(?:at|join)\s+([A-Z][\w&.\- ]{1,30}?)(?:[,.!]|\s+(?:is|as|we|and|to)\b)", text[:600])
        org = None
        for suffix in _ORG_SUFFIXES:
            org = org or re.search(rf"\b((?:[A-Z][\w&.'-]*\s+){{1,4}}{suffix})\b", text[:2500])
        company = at.group(1).strip() if at else org.group(1).strip() if org else "Your job description"
        company = re.sub(r"\s+", " ", re.sub(r"^(?:The|the)\s+", "", company))
    location = fields.get("location") or fields.get("job location") or ""
    wt_text = f"{fields.get('work type', '')} {fields.get('workplace', '')} {text[:1500]}".lower()
    work_type = "Remote" if "remote" in wt_text else "Hybrid" if "hybrid" in wt_text else "On-site" if re.search(r"on[- ]?site|in[- ]office", wt_text) else "Not specified"
    if not location:
        location = "Remote" if work_type == "Remote" else "Not specified"

    main_text = "\n".join(sec.get("header", []) + sec.get("about", []) + sec.get("responsibilities", []) + sec.get("requirements", []))
    preferred_text = "\n".join(sec.get("preferred", []))
    found_main = sk.find_in_text(f"{title}\n{main_text}") if main_text.strip() else sk.find_in_text(text)
    found_pref = [s for s in sk.find_in_text(preferred_text) if s not in found_main]
    if len(found_main) + len(found_pref) < 2:
        raise NotAJobDescription(
            "We couldn't find any job requirements in that document.",
            hint="Upload the full job description (with responsibilities and requirements), or paste its text instead.",
        )
    # Drop a generic skill when a more specific one it stands for is present
    # ("APIs" next to "REST APIs").
    found_all = set(found_main + found_pref)
    umbrella = {"APIs", "Cloud Platforms", "NoSQL", "Infrastructure as Code", "Monitoring", "Data Visualization", "Security Fundamentals", "Spring"}
    generic = {s for s in found_all & umbrella if any(x in found_all for x in sk.info(s).get("satisfied_by", []))}
    found_main = [s for s in found_main if s not in generic]
    found_pref = [s for s in found_pref if s not in generic]
    required, preferred = found_main[:16], (found_main[16:] + found_pref)[:10]

    req_text = "\n".join(sec.get("requirements", [])) or text
    months = re.search(r"(\d{1,2})\s*months?[’']?\s+(?:of\s+)?(?:\w+\s+){0,3}experience", req_text, re.I)
    years_match = _YEARS.search(req_text)
    years = int(years_match.group(1)) if years_match and int(years_match.group(1)) <= 20 else None
    experience = (f"{years_match.group(1)}–{years_match.group(2)} years" if years_match and years_match.group(2) else f"{years}+ years") if years is not None else "Not specified"
    if years is None and months:
        experience = f"{months.group(1)}+ months"
    level = _level(title, years if years is not None else (0 if months else None))

    about = sec.get("about") or [l for l in sec.get("header", []) if len(l) > 60]
    summary = " ".join(about)
    if len(summary) > 320:
        summary = summary[:320].rsplit(" ", 1)[0] + "…"
    if not summary:
        summary = f"{title} role requiring {', '.join(required[:4])}."

    responsibilities = [_clean(l) for l in sec.get("responsibilities", []) if len(_clean(l)) > 12][:10]
    requirements = [_clean(l) for l in sec.get("requirements", []) if len(_clean(l)) > 8][:10]
    if not responsibilities and not requirements:  # unstructured text: keep its bullet lines
        requirements = [_clean(l) for l in body if _BULLET.match(l) and len(_clean(l)) > 8][:10]

    # Letters only (ignores spacing, line breaks and PDF page numbers), so the
    # same posting pasted or uploaded as a PDF is recognised as one job.
    digest = hashlib.sha1(re.sub(r"[^a-z]+", "", text.lower()).encode("utf-8")).hexdigest()[:10]
    extras = {k: fields[k] for k in ("salary", "salary range", "pay", "compensation", "grade", "contract", "hours", "closing date") if k in fields}
    job = {
        "id": f"jd-{digest}",
        "title": title[:90],
        "company": company[:60],
        "location": location[:80],
        "work_type": work_type,
        "level": level,
        "experience": experience,
        "summary": summary,
        "required_skills": required,
        "preferred_skills": preferred,
        "responsibilities": responsibilities,
        "requirements": requirements,
        "role": _best_role(required, f"{title}\n{text}"),
        "source_name": "Your upload",
        "source_url": None,
        "retrieved_at": date.today().isoformat(),
        "source_note": f"Uploaded by you from {source_label}. Stored only on this machine; skills and sections were extracted automatically.",
        "details": extras,
        "full_text": text[:20000],
    }
    (job_uploads_dir() / f"{job['id']}.json").write_text(json.dumps(job, indent=2, ensure_ascii=False), encoding="utf-8")
    return job


def parse_job_file(content: bytes, filename: str, extension: str) -> Dict[str, Any]:
    return parse_job_description(extract_document(content, extension).text, filename)


def parse_job_text(text: str) -> Dict[str, Any]:
    return parse_job_description(extract_from_plain_text(text).text, "pasted text")


def delete_uploaded_job(job_id: str) -> bool:
    if not re.fullmatch(r"jd-[0-9a-f]{10}", job_id):
        return False
    path = job_uploads_dir() / f"{job_id}.json"
    if path.exists():
        path.unlink()
        return True
    return False
