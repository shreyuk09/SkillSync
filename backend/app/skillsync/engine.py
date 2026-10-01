"""Deterministic career analysis: job matching, resume scores, skill gaps,
improvements and keywords.

None of this calls an LLM. Every number is computed from the resume JSON and
the job dataset, so it is instant, repeatable and explainable -- the UI can
always show *why* a score is what it is. Results are cached per resume content
hash + dataset version, so editing a JSON file invalidates them automatically.
"""

import math
import re
from collections import Counter
from functools import lru_cache
from typing import Any, Dict, List, Optional, Set, Tuple

from app.skillsync import skills as sk
from app.skillsync.dataset import get_dataset, get_job, get_resume

STRONG_MATCH = 75
RELEVANT_MATCH = 45

_VAGUE = re.compile(
    r"^(worked on|worked with|responsible for|helped( with)?|did|made|involved in|"
    r"assisted|participated in|handled|fixed bugs|was part of)\b",
    re.I,
)
_METRIC = re.compile(r"\d+\s?%|\d+\s?(ms|x|k|m|\+)\b|[₹$€£]\s?\d|\b\d{2,}\b|\d+\s?(crore|lakh|million|users|teams|services)", re.I)
_ACTION = re.compile(
    r"^(built|designed|developed|led|created|cut|reduced|improved|increased|launched|migrated|"
    r"automated|implemented|introduced|wrote|shipped|optimi[sz]ed|redesigned|ran|operated|"
    r"triaged|investigated|tuned|mentored|converted|set up|added|moved|maintained|managed|"
    r"delivered|owned|analy[sz]ed|trained|deployed|published|architected|established)\b",
    re.I,
)


# ---------------------------------------------------------------------------
# Resume helpers
# ---------------------------------------------------------------------------
def _key(resume_id: str) -> Tuple[str, str, str]:
    ds = get_dataset()
    return resume_id, ds.resume_hashes.get(resume_id, ""), ds.jobs_version


def resume_text(resume: Dict[str, Any]) -> str:
    parts = [resume.get("headline", ""), resume.get("summary", "")]
    for job in resume.get("experience", []):
        parts.append(f"{job.get('title', '')} {job.get('company', '')}")
        parts.extend(job.get("bullets", []))
    for project in resume.get("projects", []):
        parts.append(f"{project.get('name', '')} {' '.join(project.get('tech', []))} {project.get('description', '')}")
    skills = resume.get("skills", {})
    parts.extend(skills.get("technical", []) + skills.get("soft", []))
    parts.extend(resume.get("certifications", []))
    return "\n".join(p for p in parts if p)


def bullets(resume: Dict[str, Any]) -> List[Dict[str, str]]:
    out = []
    for job in resume.get("experience", []):
        for text in job.get("bullets", []):
            out.append({"where": f"{job.get('title', 'Experience')} · {job.get('company', '')}".strip(" ·"), "text": text})
    return out


def listed_skills(resume: Dict[str, Any]) -> Set[str]:
    s = resume.get("skills", {})
    return sk.canonical_set(s.get("technical", []) + s.get("soft", []))


def all_skills(resume: Dict[str, Any]) -> Set[str]:
    """Listed skills plus anything the experience and projects clearly mention."""
    have = set(listed_skills(resume))
    for project in resume.get("projects", []):
        have |= sk.canonical_set(project.get("tech", []))
    # Evidence text only: the summary often states goals ("keen to work on
    # distributed systems"), which must not count as having the skill.
    evidence = [b["text"] for b in bullets(resume)] + [p.get("description", "") for p in resume.get("projects", [])]
    have |= set(sk.find_in_text("\n".join(evidence + resume.get("certifications", []))))
    return have


def evidence_for(resume: Dict[str, Any], skill: str) -> List[Dict[str, str]]:
    """Where in the resume a skill is actually demonstrated (not just listed)."""
    found = []
    for item in bullets(resume):
        if skill in sk.find_in_text(item["text"]):
            found.append({"where": item["where"], "text": item["text"]})
    for project in resume.get("projects", []):
        tech = sk.canonical_set(project.get("tech", []))
        if skill in tech or skill in sk.find_in_text(project.get("description", "")):
            found.append({"where": f"Project · {project.get('name')}", "text": project.get("description", "")})
    for cert in resume.get("certifications", []):
        if skill in sk.find_in_text(cert):
            found.append({"where": "Certification", "text": cert})
    return found[:3]


def years_of(resume: Dict[str, Any]) -> float:
    if resume.get("years_experience") is not None:
        return float(resume["years_experience"])
    years = 0.0
    for job in resume.get("experience", []):
        try:
            start = int(str(job.get("start", ""))[:4])
            end_raw = str(job.get("end", ""))
            end = 2026 if "present" in end_raw.lower() else int(end_raw[:4])
            years += max(0, end - start)
        except ValueError:
            continue
    return years


def job_min_years(job: Dict[str, Any]) -> float:
    text = f"{job.get('experience', '')}"
    number = re.search(r"(\d+)", text)
    if number and "month" in text.lower():
        return round(int(number.group(1)) / 12, 1)
    if number:
        return float(number.group(1))
    level = f"{job.get('level', '')} {text}".lower()
    if any(w in level for w in ("entry", "new grad", "graduate", "early", "intern")):
        return 0.0
    if "senior" in level or "experienced" in level:
        return 4.0
    return 2.0


# ---------------------------------------------------------------------------
# Lightweight TF-IDF for role/text similarity (deterministic, instant)
# ---------------------------------------------------------------------------
_TOKEN = re.compile(r"[a-z][a-z0-9+#.]+")
_STOP = set("and the for with from into that this are was were have has had you your our their its them they not but all any can will who what when where how per via using use used".split())


def _tokens(text: str) -> List[str]:
    return [t for t in _TOKEN.findall(text.lower()) if t not in _STOP and len(t) > 2]


@lru_cache(maxsize=4)
def _idf(kb_version: str) -> Dict[str, float]:
    docs = [set(_tokens(_job_text(j))) for j in get_dataset().jobs.values()]
    df = Counter(t for d in docs for t in d)
    n = len(docs) or 1
    return {t: math.log((n + 1) / (c + 1)) + 1 for t, c in df.items()}


def _job_text(job: Dict[str, Any]) -> str:
    return " ".join([job.get("title", ""), job.get("summary", ""), " ".join(job.get("responsibilities", [])),
                     " ".join(job.get("required_skills", []) + job.get("preferred_skills", []))])


def _similarity(a: str, b: str) -> float:
    idf = _idf(get_dataset().jobs_version)
    va, vb = Counter(_tokens(a)), Counter(_tokens(b))
    wa = {t: c * idf.get(t, 1.0) for t, c in va.items()}
    wb = {t: c * idf.get(t, 1.0) for t, c in vb.items()}
    dot = sum(w * wb.get(t, 0) for t, w in wa.items())
    na = math.sqrt(sum(w * w for w in wa.values()))
    nb = math.sqrt(sum(w * w for w in wb.values()))
    return dot / (na * nb) if na and nb else 0.0


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------
def _coverage(required: List[str], have: Set[str]) -> Tuple[float, List[Dict], List[Dict], List[str]]:
    matched, partial, missing = [], [], []
    points = 0.0
    for skill in required:
        via = sk.covered_by(skill, have)
        if via:
            matched.append({"skill": skill, "via": via if via != skill else None})
            points += 1
            continue
        near = sk.related_partial(skill, have)
        if near:
            partial.append({"skill": skill, "related": near})
            points += 0.4
        else:
            missing.append(skill)
    return (points / len(required) if required else 1.0), matched, partial, missing


def score_job(resume: Dict[str, Any], job: Dict[str, Any], extra: Optional[Set[str]] = None) -> Dict[str, Any]:
    have = all_skills(resume) | (extra or set())
    req, req_matched, req_partial, req_missing = _coverage(job.get("required_skills", []), have)
    pref, pref_matched, pref_partial, pref_missing = _coverage(job.get("preferred_skills", []), have)

    if resume.get("target_role") == job["role"]:
        role_fit = 1.0
    else:
        role_fit = min(1.0, _similarity(resume_text(resume), _job_text(job)) * 2.2)

    need, has = job_min_years(job), years_of(resume)
    exp_fit = 1.0 if has >= need else max(0.2, 1 - (need - has) / max(need, 1) * 0.8)

    score = round(100 * (0.55 * req + 0.15 * pref + 0.15 * role_fit + 0.15 * exp_fit))
    return {
        "score": int(score),
        "breakdown": {
            "required_skills": round(req * 100),
            "preferred_skills": round(pref * 100),
            "role_fit": round(role_fit * 100),
            "experience_fit": round(exp_fit * 100),
        },
        "matched_skills": [m["skill"] for m in req_matched + pref_matched],
        "matched_detail": req_matched + pref_matched,
        "partial_skills": req_partial + pref_partial,
        "missing_skills": req_missing,
        "missing_preferred": pref_missing,
        "years": {"resume": has, "job_min": need},
    }


def label_for(score: int) -> str:
    if score >= STRONG_MATCH:
        return "Strong match"
    if score >= 60:
        return "Good match"
    if score >= RELEVANT_MATCH:
        return "Fair match"
    return "Low match"


def _explain(resume: Dict[str, Any], job: Dict[str, Any], m: Dict[str, Any]) -> str:
    req = job.get("required_skills", [])
    have_req = [s for s in req if s in m["matched_skills"]]
    parts = [f"You cover {len(have_req)} of {len(req)} required skills"]
    if have_req:
        parts[0] += f" ({', '.join(have_req[:4])}{'…' if len(have_req) > 4 else ''})"
    parts[0] += "."
    has, need = m["years"]["resume"], m["years"]["job_min"]
    if has >= need:
        parts.append(f"Your {has:g} year{'s' if has != 1 else ''} of experience fits the {job.get('experience', 'stated').lower()} level.")
    else:
        parts.append(f"The role asks for about {need:g}+ years; your resume shows {has:g}.")
    if m["missing_skills"]:
        parts.append(f"Biggest gap: {', '.join(m['missing_skills'][:3])}.")
    elif m["partial_skills"]:
        parts.append(f"Strengthen {m['partial_skills'][0]['skill']} to move higher.")
    return " ".join(parts)


def job_card(job: Dict[str, Any]) -> Dict[str, Any]:
    keep = ("id", "title", "company", "location", "work_type", "level", "experience", "role", "role_title",
            "summary", "required_skills", "preferred_skills", "source_name", "source_url", "retrieved_at", "source_note",
            "uploaded")
    return {k: job.get(k) for k in keep}


@lru_cache(maxsize=64)
def _matches(key: Tuple[str, str, str]) -> List[Dict[str, Any]]:
    resume = get_resume(key[0])
    out = []
    for job in get_dataset().jobs.values():
        m = score_job(resume, job)
        out.append({
            **job_card(job),
            "match": m["score"],
            "label": label_for(m["score"]),
            "matched_skills": m["matched_skills"],
            "partial_skills": [p["skill"] for p in m["partial_skills"]],
            "missing_skills": m["missing_skills"] + m["missing_preferred"][:2],
            "explanation": _explain(resume, job, m),
            "breakdown": m["breakdown"],
        })
    out.sort(key=lambda j: (-j["match"], j["id"]))
    return out


def matches(resume_id: str) -> List[Dict[str, Any]]:
    return _matches(_key(resume_id))


def target_role(resume_id: str) -> str:
    resume = get_resume(resume_id)
    roles = get_dataset().roles
    if resume.get("target_role") in roles:
        return resume["target_role"]
    by_role: Dict[str, List[int]] = {}
    for job in matches(resume_id):
        if job.get("uploaded"):
            continue
        by_role.setdefault(job["role"], []).append(job["match"])
    return max(by_role, key=lambda r: max(by_role[r])) if by_role else next(iter(roles), "")


def job_detail(resume_id: str, job_id: str) -> Dict[str, Any]:
    resume, job = get_resume(resume_id), get_job(job_id)
    m = score_job(resume, job)
    have_list = []
    for item in m["matched_detail"]:
        have_list.append({"skill": item["skill"], "via": item["via"], "evidence": evidence_for(resume, item["via"] or item["skill"])})
    # What would each missing skill be worth? Re-score with it added.
    boosts = []
    for skill in m["missing_skills"] + [p["skill"] for p in m["partial_skills"]] + m["missing_preferred"]:
        gain = score_job(resume, job, extra={skill})["score"] - m["score"]
        if gain > 0:
            boosts.append({"skill": skill, "gain": gain, "how_to_learn": sk.info(skill).get("how_to_learn", "")})
    boosts.sort(key=lambda b: -b["gain"])

    why = []
    if m["breakdown"]["required_skills"] >= 70:
        why.append(f"Strong overlap with the required skills ({m['breakdown']['required_skills']}% covered).")
    if resume.get("target_role") == job["role"]:
        why.append(f"Your resume targets {job['role_title']} roles, which is what this posting is.")
    if m["years"]["resume"] >= m["years"]["job_min"]:
        why.append("Your experience level fits what the role asks for.")
    else:
        why.append(f"Experience is below the stated level ({m['years']['resume']:g} vs about {m['years']['job_min']:g}+ years), which lowers the score.")
    ev_count = sum(1 for h in have_list if h["evidence"])
    if ev_count:
        why.append(f"{ev_count} of your matched skills are backed by real work or projects in your resume.")

    return {
        **job_card(job),
        "responsibilities": job.get("responsibilities", []),
        "requirements": job.get("requirements", []),
        "full_text": job.get("full_text") if job.get("uploaded") else None,
        "match": m["score"],
        "label": label_for(m["score"]),
        "breakdown": m["breakdown"],
        "explanation": _explain(resume, job, m),
        "why_you_match": why,
        "skills_you_have": have_list,
        "skills_partial": m["partial_skills"],
        "skills_missing": [{"skill": s, "required": True, "how_to_learn": sk.info(s).get("how_to_learn", "")} for s in m["missing_skills"]]
        + [{"skill": s, "required": False, "how_to_learn": sk.info(s).get("how_to_learn", "")} for s in m["missing_preferred"]],
        "recommended_improvements": boosts[:4],
    }


# ---------------------------------------------------------------------------
# Resume analysis
# ---------------------------------------------------------------------------
def _bullet_quality(text: str) -> Dict[str, bool]:
    t = text.strip()
    return {
        "vague": bool(_VAGUE.search(t)) or len(t) < 35,
        "metric": bool(_METRIC.search(t)),
        "action": bool(_ACTION.search(t)),
    }


@lru_cache(maxsize=64)
def _analysis(key: Tuple[str, str, str]) -> Dict[str, Any]:
    resume_id = key[0]
    resume = get_resume(resume_id)
    role = get_dataset().roles.get(target_role(resume_id), {})
    role_jobs = [j for j in matches(resume_id) if j["role"] == role.get("role")]
    have = all_skills(resume)
    summary_words = len((resume.get("summary") or "").split())
    items = bullets(resume)
    quality = [_bullet_quality(b["text"]) for b in items]
    vague = [b for b, q in zip(items, quality) if q["vague"]]
    with_metric = sum(q["metric"] for q in quality)
    projects = resume.get("projects", [])

    # ATS readiness: can a parser find the standard pieces?
    ats_checks = {
        "Contact email": bool(resume.get("email")),
        "Headline / title": bool(resume.get("headline")),
        "Professional summary": summary_words >= 12,
        "Work experience section": bool(resume.get("experience")),
        "Education section": bool(resume.get("education")),
        "Skills section": len(listed_skills(resume)) >= 5,
        "Dated roles": all(j.get("start") for j in resume.get("experience", [])) if resume.get("experience") else False,
    }
    ats = round(100 * sum(ats_checks.values()) / len(ats_checks))

    skill_rel = round(sum(j["breakdown"]["required_skills"] for j in role_jobs) / len(role_jobs)) if role_jobs else 0

    def project_points(p: Dict[str, Any]) -> float:
        desc = p.get("description", "")
        return (0.3 * (len(p.get("tech", [])) >= 2) + 0.3 * (len(desc) >= 60) + 0.25 * bool(_METRIC.search(desc) or re.search(r"\b(with|using)\b", desc))
                + 0.15 * bool(p.get("link")))
    project_strength = round(100 * min(1.0, (sum(project_points(p) for p in projects) / max(2, len(projects))) * (1 if len(projects) >= 2 else 0.75))) if projects else 10

    if items:
        strong_frac = sum(1 for q in quality if q["action"] and not q["vague"]) / len(items)
        metric_frac = with_metric / len(items)
        exp_clarity = round(100 * (0.6 * strong_frac + 0.4 * metric_frac))
    else:
        exp_clarity = 25

    core = role.get("core_skills", [])
    core_have = [s for s in core if sk.covered_by(s, have)]
    keyword_cov = round(100 * len(core_have) / len(core)) if core else 0

    struct_checks = [
        12 <= summary_words <= 70,
        all(2 <= len(j.get("bullets", [])) <= 6 for j in resume.get("experience", [])) if resume.get("experience") else False,
        len(vague) <= 1,
        len(projects) >= 2,
        bool(resume.get("certifications")) or bool(resume.get("achievements")),
    ]
    structure = round(100 * sum(struct_checks) / len(struct_checks))

    scores = [
        {"key": "ats", "label": "ATS Readiness", "value": ats},
        {"key": "skills", "label": "Skill Relevance", "value": skill_rel},
        {"key": "projects", "label": "Project Strength", "value": project_strength},
        {"key": "experience", "label": "Experience Clarity", "value": exp_clarity},
        {"key": "keywords", "label": "Keyword Coverage", "value": keyword_cov},
        {"key": "structure", "label": "Structure", "value": structure},
    ]
    weights = {"ats": 0.15, "skills": 0.25, "projects": 0.15, "experience": 0.2, "keywords": 0.15, "structure": 0.1}
    overall = round(sum(s["value"] * weights[s["key"]] for s in scores))

    working, needs, changes = [], [], []
    if with_metric >= 2:
        working.append(f"{with_metric} experience bullet{'s' if with_metric != 1 else ''} include measurable results.")
    if len(core_have) >= max(1, len(core) // 2):
        working.append(f"Covers {len(core_have)} of {len(core)} core {role.get('title', '')} skills.")
    if resume.get("certifications"):
        working.append(f"Certification{'s' if len(resume['certifications']) > 1 else ''} listed: {', '.join(resume['certifications'][:2])}.")
    if len(projects) >= 2:
        working.append(f"{len(projects)} projects show hands-on work beyond the job.")
    if 12 <= summary_words <= 70:
        working.append("A clear summary tells a reader what you do in one glance.")

    if vague:
        needs.append(f"{len(vague)} bullet{'s are' if len(vague) != 1 else ' is'} vague (e.g. “{vague[0]['text']}”).")
        changes.append("Rewrite vague bullets as action + what you built + measurable result.")
    if items and with_metric < max(1, len(items) // 2):
        needs.append("Most bullets don't show impact with numbers.")
        changes.append("Add a number to at least half your bullets: time saved, users, % improvement, scale.")
    missing_core = [s for s in core if s not in core_have]
    if missing_core:
        needs.append(f"Missing core {role.get('title', '')} skills: {', '.join(missing_core[:4])}.")
        changes.append(f"Build one project that uses {', '.join(missing_core[:2])} and add it to your resume.")
    if summary_words < 12:
        needs.append("The summary is missing or too short to describe your focus.")
        changes.append("Write a 2–3 sentence summary: role, years, strongest skills, what you want next.")
    if len(projects) < 2:
        needs.append("Fewer than two projects.")
        changes.append("Add a second project that shows skills your target role asks for.")
    if not any(p.get("link") for p in projects):
        changes.append("Link your projects (GitHub or a live demo) so reviewers can verify them.")

    return {
        "resume_id": resume_id,
        "overall": overall,
        "grade": "Excellent" if overall >= 85 else "Good" if overall >= 70 else "Fair" if overall >= 50 else "Needs work",
        "target_role": role.get("role"),
        "target_role_title": role.get("title"),
        "scores": scores,
        "ats_checks": [{"label": k, "ok": v} for k, v in ats_checks.items()],
        "whats_working": working,
        "needs_improvement": needs,
        "recommended_changes": changes,
        "vague_bullets": vague,
        "bullet_stats": {"total": len(items), "with_metrics": with_metric, "vague": len(vague)},
    }


def analysis(resume_id: str) -> Dict[str, Any]:
    return _analysis(_key(resume_id))


# ---------------------------------------------------------------------------
# Skill gaps
# ---------------------------------------------------------------------------
def _role_requirements(role_id: str) -> List[Tuple[str, int, bool]]:
    """(skill, how many postings ask for it, is it required somewhere)."""
    ds = get_dataset()
    role = ds.roles[role_id]
    counts: Counter = Counter()
    required: Set[str] = set()
    for jid in role["posting_ids"]:
        job = ds.jobs[jid]
        counts.update(job.get("required_skills", []))
        counts.update(job.get("preferred_skills", []))
        required |= set(job.get("required_skills", []))
    for skill in role["core_skills"]:
        counts[skill] += 1
        required.add(skill)
    ranked = sorted(counts, key=lambda s: (-(s in required), -counts[s], s))
    return [(s, counts[s], s in required) for s in ranked[:14]]


def gaps(resume_id: str, role_id: Optional[str] = None, job_id: Optional[str] = None) -> Dict[str, Any]:
    return _gaps(_key(resume_id), role_id or "", job_id or "")


@lru_cache(maxsize=128)
def _gaps(key: Tuple[str, str, str], role_id: str, job_id: str) -> Dict[str, Any]:
    resume_id = key[0]
    resume = get_resume(resume_id)
    ds = get_dataset()
    have = all_skills(resume)
    listed = listed_skills(resume)

    if job_id:
        job = get_job(job_id)
        reqs = [(s, 1, True) for s in job.get("required_skills", [])] + [(s, 1, False) for s in job.get("preferred_skills", [])]
        target = {"type": "job", "id": job_id, "title": f"{job['title']} · {job['company']}"}
    else:
        role_id = role_id if role_id in ds.roles else target_role(resume_id)
        reqs = _role_requirements(role_id)
        target = {"type": "role", "id": role_id, "title": ds.roles[role_id]["title"]}

    rows = []
    for skill, freq, required in reqs:
        via = sk.covered_by(skill, have)
        info = sk.info(skill)
        if via:
            ev = evidence_for(resume, via)
            if ev:
                status, gap = "strong", "None — shown in your work"
                rec = "Keep it prominent; mention it in your top bullets."
            else:
                status, gap = "improve", "Listed but not shown in any role or project"
                rec = f"Add a bullet or project that uses {via} with a concrete result."
            current = via if via in listed or ev else via
        else:
            near = sk.related_partial(skill, have)
            ev = []
            if near:
                status, current = "improve", near
                gap = f"Related experience ({near}) but not {skill} itself"
            else:
                status, current, gap = "missing", None, "Not found in your resume"
            rec = info.get("how_to_learn") or f"Learn the basics of {skill} and apply it in a project."
        priority = "High" if status == "missing" and required and freq >= 2 else "High" if status == "missing" and required else "Medium" if status != "strong" else "Low"
        rows.append({
            "skill": skill,
            "category": info.get("category", "Other"),
            "status": status,
            "current": current,
            "required_level": "Required" if required else "Nice to have",
            "demand": freq,
            "gap": gap,
            "recommendation": rec,
            "priority": priority,
            "evidence": ev[:1],
        })
    order = {"missing": 0, "improve": 1, "strong": 2}
    rows.sort(key=lambda r: (order[r["status"]], r["required_level"] != "Required", -r["demand"]))
    counts = Counter(r["status"] for r in rows)
    return {
        "resume_id": resume_id,
        "target": target,
        "summary": {"strong": counts["strong"], "improve": counts["improve"], "missing": counts["missing"], "total": len(rows)},
        "skills": rows,
        "roles": [{"id": r["role"], "title": r["title"]} for r in ds.roles.values()],
    }


# ---------------------------------------------------------------------------
# Keywords + improvements
# ---------------------------------------------------------------------------
def keywords(resume_id: str) -> Dict[str, Any]:
    resume = get_resume(resume_id)
    role_id = target_role(resume_id)
    reqs = _role_requirements(role_id)
    have = all_skills(resume)
    strong, missing, recommended = [], [], []
    for skill, freq, required in reqs:
        via = sk.covered_by(skill, have)
        if via:
            strong.append({"keyword": skill, "demand": freq, "shown": bool(evidence_for(resume, via))})
        elif required:
            near = sk.related_partial(skill, have)
            (recommended if near else missing).append({"keyword": skill, "demand": freq, "related": near})
        else:
            recommended.append({"keyword": skill, "demand": freq, "related": sk.related_partial(skill, have)})
    return {
        "target_role": role_id,
        "strong": strong,
        "missing": missing,
        "recommended": recommended,
        "note": "Only add a keyword if you have genuinely used it. Put it inside a bullet that shows how — a list of keywords with no evidence reads as stuffing to recruiters and ATS alike.",
    }


@lru_cache(maxsize=64)
def _improvements(key: Tuple[str, str, str]) -> List[Dict[str, Any]]:
    resume_id = key[0]
    resume = get_resume(resume_id)
    a = analysis(resume_id)
    g = gaps(resume_id)
    kw = keywords(resume_id)
    top = matches(resume_id)[:3]
    role_title = a["target_role_title"] or "your target role"
    items: List[Dict[str, Any]] = []

    def add(category, title, problem, why, action, kws=None, priority="Medium", example=None):
        items.append({"id": f"{category.lower().replace(' ', '-')}-{len(items) + 1}", "category": category, "title": title,
                      "problem": problem, "why": why, "action": action, "keywords": kws or [], "priority": priority,
                      "example": example})

    # Resume
    words = len((resume.get("summary") or "").split())
    if words < 12:
        add("Resume", "Write a focused summary", "Your summary is missing or only a few words long.",
            "Recruiters spend seconds on a first pass; the summary tells them which role you fit.",
            f"Write 2–3 sentences: your role, years of experience, 3 strongest skills and the {role_title} work you want next.",
            [k["keyword"] for k in kw["strong"][:3]], "High")
    elif words > 70:
        add("Resume", "Tighten your summary", "Your summary is long.", "Long summaries get skimmed past.",
            "Cut it to 2–3 sentences focused on the role you want.", [], "Low")
    if not any(p.get("link") for p in resume.get("projects", [])):
        add("Resume", "Link to your work", "None of your projects has a link.",
            "A GitHub repo or live demo lets a reviewer verify your skills in one click.",
            "Add a GitHub or demo link under each project, and your GitHub/LinkedIn in the header.", [], "Medium")
    pending = [c for c in resume.get("certifications", []) if "progress" in c.lower()]
    if pending:
        add("Resume", "Finish or clarify in-progress certifications", f"“{pending[0]}” is listed as in progress.",
            "Unfinished credentials carry little weight and can raise questions.",
            "Add an expected completion date, or move it to a 'Currently learning' line.", [], "Low")

    # Experience
    vague = a["vague_bullets"]
    if vague:
        quoted = "; ".join(f"“{v['text']}”" for v in vague[:3])
        add("Experience", f"Rewrite {len(vague)} vague bullets" if len(vague) > 1 else "Rewrite a vague bullet",
            f"{quoted} {'don’t' if len(vague) > 1 else 'doesn’t'} say what you did or what changed.",
            "Specific bullets with outcomes are what separate candidates with similar titles.",
            "Rewrite each as: action verb + what you built or fixed + tools + measurable result.",
            [], "High", {"before": vague[0]["text"], "after": "e.g. “Fixed 25+ production bugs in the invoicing module (Java, SQL), cutting support tickets by 30%.” — use your real numbers."})
    stats = a["bullet_stats"]
    if stats["total"] and stats["with_metrics"] < stats["total"] / 2:
        add("Experience", "Show impact with numbers", f"Only {stats['with_metrics']} of {stats['total']} bullets include a number.",
            "Numbers make impact concrete and easy to compare.", "Add scale, time saved, % improvement or users to at least half your bullets.", [], "High")
    if not resume.get("experience"):
        add("Experience", "Add practical experience", "No work experience or internships are listed.",
            "Even short internships, freelance or open-source work shows you can deliver in a team.",
            "Add internships, freelance work, open-source contributions or a significant team project as experience.", [], "High")

    # Skills
    for row in [r for r in g["skills"] if r["status"] == "missing"][:3]:
        add("Skills", f"Learn {row['skill']}", f"{row['skill']} is {row['required_level'].lower()} for {g['target']['title']} roles and isn't in your resume.",
            f"It appears in {row['demand']} of the {g['target']['title']} requirements in our dataset.", row["recommendation"], [row["skill"]], row["priority"])
    for row in [r for r in g["skills"] if r["status"] == "improve" and r["current"] == r["skill"]][:2]:
        add("Skills", f"Prove your {row['skill']}", f"{row['skill']} is listed but not shown in any role or project.",
            "Listed skills without evidence are easy to discount.", row["recommendation"], [row["skill"]], "Medium")

    # Projects
    projects = resume.get("projects", [])
    missing_core = [r["skill"] for r in g["skills"] if r["status"] != "strong" and r["required_level"] == "Required"][:3]
    if len(projects) < 2 or missing_core:
        add("Projects", "Add a project aimed at your target role",
            f"You have {len(projects)} project{'s' if len(projects) != 1 else ''}" + (f", and none use {', '.join(missing_core[:2])}." if missing_core else "."),
            "A focused project is the fastest way to show a skill you haven't used at work.",
            f"Build a small, complete {role_title} project using {', '.join(missing_core[:3]) or 'the core skills'}; include a README, tests and a link.",
            missing_core, "High" if len(projects) < 2 else "Medium")
    for p in projects:
        if len(p.get("description", "")) < 60:
            add("Projects", f"Expand “{p.get('name')}”", "The project description is one short line.",
                "Reviewers can't tell what you built or how hard it was.",
                "Add what problem it solves, your key technical decisions and a result (users, speed, accuracy).", p.get("tech", [])[:3], "Medium")

    # Keywords
    if kw["missing"]:
        add("Keywords", "Cover missing role keywords", f"Common {role_title} keywords are absent: {', '.join(k['keyword'] for k in kw['missing'][:5])}.",
            "Applicant tracking systems and recruiters search for these terms.",
            "Only add ones you genuinely know, inside bullets that show how you used them. Learn the rest before adding them.",
            [k["keyword"] for k in kw["missing"][:5]], "Medium")
    hidden = [k["keyword"] for k in kw["strong"] if not k["shown"]]
    if hidden:
        add("Keywords", "Move keywords into your bullets", f"{', '.join(hidden[:4])} appear only in your skills list.",
            "Keywords inside achievements count for more than a list.", "Mention each in the bullet or project where you used it.", hidden[:4], "Low")

    # Job match
    if top:
        best = top[0]
        detail = job_detail(resume_id, best["id"])
        boost = detail["recommended_improvements"][:2]
        if boost:
            gain = sum(b["gain"] for b in boost)
            add("Job Match", f"Raise your match for {best['title']}",
                f"Your best match ({best['company']}) is {best['match']}%. Missing: {', '.join(b['skill'] for b in boost)}.",
                f"Adding these (for real) would lift this match by about {gain} points, to ~{min(100, best['match'] + gain)}%.",
                "; ".join(f"{b['skill']}: {b['how_to_learn']}" for b in boost), [b["skill"] for b in boost], "High" if best["match"] < STRONG_MATCH else "Medium")

    # Interview preparation
    if top:
        best = get_job(top[0]["id"])
        m = score_job(resume, best)
        talk = m["matched_skills"][:3]
        add("Interview Preparation", f"Prepare stories for {best['title']}",
            "Interviewers will probe the skills this role depends on.",
            "Concrete stories are what turn a resume match into an offer.",
            f"Prepare a 2-minute STAR story each for {', '.join(talk) or 'your main skills'}, and an honest plan for {', '.join(m['missing_skills'][:2]) or 'any gaps'}."
            + (f" Expect questions about: {best['responsibilities'][0].rstrip('.').lower()}." if best.get("responsibilities") else ""),
            talk + m["missing_skills"][:2], "Medium")

    rank = {"High": 0, "Medium": 1, "Low": 2}
    items.sort(key=lambda i: rank[i["priority"]])
    return items


def improvements(resume_id: str) -> Dict[str, Any]:
    items = _improvements(_key(resume_id))
    return {
        "resume_id": resume_id,
        "categories": ["Resume", "Skills", "Projects", "Experience", "Keywords", "Job Match", "Interview Preparation"],
        "items": items,
        "counts": dict(Counter(i["priority"] for i in items)),
        "keywords": keywords(resume_id),
    }


# ---------------------------------------------------------------------------
# Dashboard + profile
# ---------------------------------------------------------------------------
def profile(resume: Dict[str, Any]) -> Dict[str, Any]:
    skills = resume.get("skills", {})
    edu = resume.get("education", [])
    return {
        "id": resume["id"],
        "name": resume.get("name"),
        "headline": resume.get("headline"),
        "location": resume.get("location"),
        "email": resume.get("email"),
        "summary": resume.get("summary"),
        "years_experience": years_of(resume),
        "education": edu,
        "experience": resume.get("experience", []),
        "projects": resume.get("projects", []),
        "certifications": resume.get("certifications", []),
        "achievements": resume.get("achievements", []),
        "technical_skills": skills.get("technical", []),
        "soft_skills": skills.get("soft", []),
        "source": resume.get("source", {}),
        "target_role": resume.get("target_role"),
    }


def completion(resume: Dict[str, Any]) -> int:
    checks = [resume.get("summary"), resume.get("experience"), resume.get("education"), resume.get("projects"),
              len(resume.get("skills", {}).get("technical", [])) >= 5, resume.get("skills", {}).get("soft"),
              resume.get("certifications"), any(p.get("link") for p in resume.get("projects", []))]
    return round(100 * sum(bool(c) for c in checks) / len(checks))


def dashboard(resume_id: str) -> Dict[str, Any]:
    resume = get_resume(resume_id)
    a = analysis(resume_id)
    ms = matches(resume_id)
    g = gaps(resume_id)
    imp = improvements(resume_id)
    return {
        "resume_id": resume_id,
        "profile": profile(resume),
        "completion": completion(resume),
        "cards": {
            "resume_score": a["overall"],
            "job_matches": sum(1 for j in ms if j["match"] >= RELEVANT_MATCH),
            "strong_matches": sum(1 for j in ms if j["match"] >= STRONG_MATCH),
            "skills_to_improve": g["summary"]["improve"] + g["summary"]["missing"],
            "total_jobs": len(ms),
        },
        "analysis": {"overall": a["overall"], "grade": a["grade"], "scores": a["scores"], "target_role_title": a["target_role_title"]},
        "top_matches": ms[:3],
        "gap_summary": g["summary"],
        "top_gaps": [r for r in g["skills"] if r["status"] != "strong"][:5],
        # one per category, so the dashboard shows three different kinds of fix
        "top_improvements": list({i["category"]: i for i in reversed(imp["items"])}.values())[::-1][:3],
    }


def clear_caches() -> None:
    for fn in (_matches, _analysis, _gaps, _improvements):
        fn.cache_clear()
