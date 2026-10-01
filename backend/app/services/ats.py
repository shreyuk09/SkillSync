"""ATS keyword analysis.

Applicant Tracking Systems scan a resume for the terms in the posting. This
module reports that coverage honestly:

* which JD keywords appear in the resume, and how often;
* which don't;
* which of the missing ones actually matter (keywords are ranked by the JD
  parser in importance order, and weighted accordingly).

Deliberately NOT keyword stuffing advice. A missing keyword is only worth
adding if the candidate genuinely has the underlying experience, and the API
response says so for every suggestion.
"""

from typing import Any, Dict, List

from app.services.skill_matching import canonical_skill, count_mentions, mentions


def _importance_for(position: int, total: int) -> str:
    """The JD parser returns keywords most-important-first."""
    if total <= 1:
        return "high"
    ratio = position / max(total - 1, 1)
    if ratio <= 0.33:
        return "high"
    if ratio <= 0.7:
        return "medium"
    return "low"


IMPORTANCE_WEIGHT = {"high": 1.0, "medium": 0.7, "low": 0.4}


def analyze_keywords(
    keywords: List[str],
    resume_text: str,
    resume_chunks: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Compare JD keywords against the resume. Pure Python, no LLM."""
    seen = set()
    rows: List[Dict[str, Any]] = []

    clean_keywords = []
    for keyword in keywords:
        keyword = str(keyword).strip()
        key = canonical_skill(keyword)
        if keyword and key not in seen:
            seen.add(key)
            clean_keywords.append(keyword)

    total = len(clean_keywords)

    for position, keyword in enumerate(clean_keywords):
        present = mentions(resume_text, keyword)
        count = count_mentions(resume_text, keyword) if present else 0
        sections = sorted(
            {
                chunk["section"]
                for chunk in resume_chunks
                if mentions(chunk["text"], keyword)
            }
        )
        importance = _importance_for(position, total)
        rows.append(
            {
                "keyword": keyword,
                "present": present,
                "count": count,
                "importance": importance,
                "weight": IMPORTANCE_WEIGHT[importance],
                "sections": sections,
            }
        )

    earned = sum(row["weight"] for row in rows if row["present"])
    possible = sum(row["weight"] for row in rows) or 1.0
    score = round(100 * earned / possible)

    matched = [row for row in rows if row["present"]]
    missing = [row for row in rows if not row["present"]]

    high_missing = [row["keyword"] for row in missing if row["importance"] == "high"]

    calculation = (
        f"Each of the {total} keywords from the job description is weighted by how "
        f"prominently the posting features it (high 1.0, medium 0.7, low 0.4). "
        f"You matched {len(matched)} of {total}, earning {earned:.1f} of "
        f"{possible:.1f} weighted points = {score}%."
    )

    return {
        "score": score,
        "total": total,
        "matched_count": len(matched),
        "missing_count": len(missing),
        "keywords": rows,
        "matched": [row["keyword"] for row in matched],
        "missing": [row["keyword"] for row in missing],
        "high_priority_missing": high_missing,
        "calculation": calculation,
        "guidance": (
            "Only add a missing keyword if you genuinely have that experience -- "
            "write it into the project or role where you actually used it. "
            "Pasting keywords into a list you can't back up fails at the interview, "
            "and modern ATS ranking notices terms that appear with no context."
        ),
    }
