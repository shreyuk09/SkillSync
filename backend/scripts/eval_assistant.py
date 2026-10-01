"""Accuracy check for the AI Career Assistant.

    cd backend && ./.venv/bin/python3 scripts/eval_assistant.py

Asks fixed questions about sample resumes and a test job description, then
checks each answer against facts computed deterministically by the engine
(not by an LLM). Reports, per question:

  recall      share of expected facts that appear in the answer
  unsupported skills the answer mentions that appear in NO retrieved source
              (a hallucination signal -- should always be empty)
  cited       whether the answer cites its sources
  refusal     for unanswerable questions, whether it correctly refused

Uses real LLM calls (about 12), so it counts against your provider quota.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.skillsync import engine, rag  # noqa: E402
from app.skillsync import skills as sk  # noqa: E402
from app.skillsync.jd_parser import delete_uploaded_job, parse_job_text  # noqa: E402

JD = """Backend Engineer (Java)
Company: Harborview Analytics
Location: Hyderabad, India (Hybrid)

About the role
We are hiring a backend engineer to build the APIs behind our analytics platform.

Responsibilities
- Design and build REST APIs in Java and Spring Boot
- Own services end to end, from design to production on AWS
- Write unit and integration tests and take part in code review
- Improve performance of PostgreSQL queries and caching with Redis

Requirements
- 2+ years of professional experience with Java
- Strong knowledge of Spring Boot, Hibernate and SQL
- Experience with Docker and CI/CD pipelines
- Good understanding of data structures and algorithms

Nice to have
- Kafka or other event streaming
- Kubernetes
"""


JD_SALARY = """Junior Software Developer
Company: Kestrel Health Ltd
Location: Leeds, UK (On-site)
Salary: £28,000 - £32,000 per year

Responsibilities
- Build features in Python and Django
- Write SQL queries and unit tests

Requirements
- 1+ years of Python experience
- Git and Docker
"""


def norm(t: str) -> str:
    t = t.replace("\u2011", "-").replace("\u2013", "-").replace("\u00a0", " ")
    return re.sub(r"\s+", " ", t.lower())


def main() -> None:
    job = parse_job_text(JD)
    jid = job["id"]
    jid2 = parse_job_text(JD_SALARY)["id"]
    try:
        detail = engine.job_detail("resume-01", jid)
        missing = [s["skill"] for s in detail["skills_missing"] if s["required"]]
        have = [s["skill"] for s in detail["skills_you_have"]]
        top = engine.matches("resume-10")[0]

        cases = [
            ("resume-01", jid, "What skills am I missing for this job?", missing, False),
            ("resume-01", jid, "Which of the required skills do I already have?", have, False),
            ("resume-01", jid, "How many years of experience does this job ask for, and do I meet it?", ["2"], False),
            ("resume-01", jid, "Does this job require Kafka?", ["kafka", "nice to have|preferred|optional|not required"], False),
            ("resume-01", None, "Where have I worked?", ["Northwind", "Brightpath"], False),
            ("resume-04", None, "What certifications do I have?", ["Solutions Architect", "Terraform"], False),
            ("resume-02", None, "What was my CGPA?", ["8.4"], False),
            ("resume-10", None, "What projects are on my resume?", ["Resume Analyzer", "E-commerce", "Movie Recommendation"], False),
            ("resume-10", None, "What is my best job match?", [top["title"].split(" –")[0]], False),
            ("resume-01", jid, "What salary does this job pay?", [], True),
            ("resume-01", None, "What is the capital of Australia?", [], True),
            ("resume-01", None, "Do I have Rust experience?", ["not|no |doesn"], False),
            ("resume-01", None, "What does Harborview Analytics want from candidates?", ["Spring Boot", "Docker"], False),
            ("resume-09", jid2, "What salary does this job pay?", ["28,000"], False),
            ("resume-09", jid2, "Am I a good fit for this job?", ["Python", "Django"], False),
        ]
        totals = {"recall": 0.0, "unsupported": 0, "cited": 0, "refusal_ok": 0, "refusal_n": 0}
        for rid, job_id, q, expect, should_refuse in cases:
            r = rag.chat(q, rid, job_id)
            ans = r.get("answer") or ""
            a = norm(ans)
            src = norm(" ".join(s["text"] for s in r["sources"]))
            hits = [e for e in expect if re.search(norm(e), a)]
            recall = len(hits) / len(expect) if expect else 1.0
            mentioned = set(sk.find_in_text(ans))
            unsupported = sorted(s for s in mentioned if norm(s) not in src
                                 and not any(norm(al) in src for al in sk.info(s).get("aliases", []))
                                 and norm(s) not in norm(q))
            refused = r["mode"] == "refused"
            cited = bool(re.search(r"\[S\d+\]", ans))
            totals["recall"] += recall
            totals["unsupported"] += len(unsupported)
            totals["cited"] += cited or refused
            if should_refuse:
                totals["refusal_n"] += 1
                totals["refusal_ok"] += refused
            flag = "OK " if recall == 1 and not unsupported and (refused == should_refuse) else "!! "
            print(f"{flag}[{rid}{' + JD' if job_id else ''}] {q}")
            print(f"    recall {recall:.0%}  missed {[e for e in expect if e not in hits]}  unsupported {unsupported}"
                  f"  cited {cited}  mode {r['mode']}")
            print("    " + ans.replace("\n", " ")[:400])
        n = len(cases)
        print("\nSUMMARY")
        print(f"  fact recall          {totals['recall'] / n:.0%}")
        print(f"  unsupported skills   {totals['unsupported']}")
        print(f"  answers with sources {totals['cited']}/{n}")
        print(f"  correct refusals     {totals['refusal_ok']}/{totals['refusal_n']}")
    finally:
        delete_uploaded_job(jid)
        delete_uploaded_job(jid2)


if __name__ == "__main__":
    main()
