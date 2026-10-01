"""Turn an uploaded resume file into the same JSON shape as the sample resumes.

Heuristic and deterministic: headings split the text into sections, bullet
lines become experience bullets, and skills are found with the skill
dictionary. The parsed resume is stored in data/storage/uploads/ and from
then on is treated exactly like a sample resume.
"""

import hashlib
import json
import re
from typing import Any, Dict, List

from app.rag.extraction import extract_document
from app.skillsync import skills as sk
from app.skillsync.dataset import get_dataset, uploads_dir

_HEADINGS = {
    "summary": r"summary|profile|objective|about me|professional summary",
    "experience": r"experience|work experience|employment|work history|internships?|professional experience",
    "education": r"education|academics?|qualifications?",
    "projects": r"projects?|personal projects|academic projects",
    "skills": r"skills|technical skills|technologies|tech stack|core competencies",
    "certifications": r"certifications?|licenses|courses",
    "achievements": r"achievements|awards|honou?rs|accomplishments",
    "interests": r"interests|hobbies",
}
_HEAD_RE = {k: re.compile(rf"^\s*({v})\s*:?\s*$", re.I) for k, v in _HEADINGS.items()}
_BULLET = re.compile(r"^\s*[-•*▪●◦·–]\s*")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
_RANGE = re.compile(r"((?:19|20)\d\d)\s*[-–—to]+\s*((?:19|20)\d\d|present|current|now)", re.I)


def _sections(text: str) -> Dict[str, List[str]]:
    sections: Dict[str, List[str]] = {"header": []}
    current = "header"
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        for key, pattern in _HEAD_RE.items():
            if pattern.match(line) and len(line) < 40:
                current = key
                sections.setdefault(key, [])
                break
        else:
            sections.setdefault(current, []).append(line)
    return sections


def _blocks(lines: List[str]) -> List[Dict[str, Any]]:
    """Group lines into entries: a non-bullet line starts a new entry."""
    blocks: List[Dict[str, Any]] = []
    for line in lines:
        if _BULLET.match(line) or (blocks and len(line) > 70):
            if not blocks:
                blocks.append({"head": "", "lines": []})
            blocks[-1]["lines"].append(_BULLET.sub("", line))
        else:
            blocks.append({"head": line, "lines": []})
    return blocks


def parse_resume(content: bytes, filename: str, extension: str) -> Dict[str, Any]:
    doc = extract_document(content, extension)
    text = doc.text
    sec = _sections(text)
    header = sec.get("header", [])
    name = next((l for l in header[:3] if 1 < len(l.split()) <= 4 and not re.search(r"[@\d|/]", l)), None)
    email = (_EMAIL.search(text) or [None])[0] if _EMAIL.search(text) else None

    experience, years = [], 0
    for b in _blocks(sec.get("experience", [])):
        rng = _RANGE.search(b["head"] + " " + " ".join(b["lines"][:1]))
        start = end = ""
        if rng:
            start, end = rng.group(1), rng.group(2)
            end_year = 2026 if not end[:1].isdigit() else int(end)
            years += max(0, end_year - int(start))
            end = "Present" if not end[:1].isdigit() else end
        head = _RANGE.sub("", b["head"]).strip(" |,-–")
        parts = re.split(r"\s+(?:at|@|\||,|–|-)\s+", head, maxsplit=1)
        experience.append({"title": parts[0] or "Role", "company": parts[1] if len(parts) > 1 else "", "location": "",
                           "start": start, "end": end, "bullets": b["lines"] or ([head] if head else [])})

    projects = []
    for b in _blocks(sec.get("projects", [])):
        desc = " ".join(b["lines"])
        projects.append({"name": re.split(r"[|:–-]", b["head"])[0].strip() or "Project",
                         "tech": sk.find_in_text(b["head"] + " " + desc), "description": desc or b["head"]})

    found = sk.find_in_text(text)
    skill_info = get_dataset().skills
    soft = [s for s in found if skill_info.get(s, {}).get("category") == "Soft skills"]
    technical = [s for s in found if s not in soft]

    summary = " ".join(sec.get("summary", []))[:900]
    education = [{"degree": b["head"], "institution": " ".join(b["lines"][:1]), "start": "", "end": ""}
                 for b in _blocks(sec.get("education", []))][:4]
    digest = hashlib.sha1(content).hexdigest()[:10]
    resume = {
        "id": f"upload-{digest}",
        "name": name or "Your Resume",
        "headline": (header[1] if len(header) > 1 and len(header[1]) < 80 and "@" not in header[1] else "Uploaded resume"),
        "target_role": None,
        "location": "",
        "email": email,
        "years_experience": years,
        "summary": summary,
        "education": education,
        "experience": experience,
        "projects": projects,
        "skills": {"technical": technical, "soft": soft},
        "certifications": sec.get("certifications", [])[:6],
        "achievements": sec.get("achievements", [])[:6],
        "interests": sec.get("interests", [])[:4],
        "source": {"type": "upload", "license": "Private — uploaded by the user, stored only on this machine.",
                   "note": f"Parsed from {filename}."},
    }
    path = uploads_dir() / f"{resume['id']}.json"
    path.write_text(json.dumps(resume, indent=2, ensure_ascii=False), encoding="utf-8")
    return resume
