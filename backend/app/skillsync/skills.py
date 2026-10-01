"""Skill vocabulary: canonical names, aliases, and "does this resume have X?"."""

import re
from functools import lru_cache
from typing import Dict, Iterable, List, Optional, Set, Tuple

from app.skillsync.dataset import get_dataset


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


@lru_cache(maxsize=8)
def _vocab(version: str) -> Tuple[Dict[str, str], List[Tuple[re.Pattern, str]]]:
    skills = get_dataset().skills
    lookup: Dict[str, str] = {}
    for name, info in skills.items():
        lookup[_norm(name)] = name
        for alias in info.get("aliases", []):
            lookup.setdefault(_norm(alias), name)
    # Longest terms first so "spring boot" wins over "spring".
    patterns = []
    for term in sorted(lookup, key=len, reverse=True):
        if len(term) <= 1:
            continue  # "C" / "R" are too ambiguous to find in free text
        escaped = re.escape(term)
        patterns.append((re.compile(rf"(?<![\w+#.]){escaped}(?![\w+#])", re.I), lookup[term]))
    return lookup, patterns


def canonical(name: str) -> Optional[str]:
    lookup, _ = _vocab(get_dataset().kb_version)
    return lookup.get(_norm(name))


def canonical_set(names: Iterable[str]) -> Set[str]:
    out = set()
    for name in names:
        out.add(canonical(name) or name.strip())
    return out


def find_in_text(text: str) -> List[str]:
    """Every known skill mentioned in free text, in order of first mention."""
    _, patterns = _vocab(get_dataset().kb_version)
    found: Dict[str, int] = {}
    remaining = text
    for pattern, name in patterns:
        match = pattern.search(remaining)
        if match:
            found.setdefault(name, match.start())
            # blank out the match so "spring boot" doesn't also count as "spring"
            remaining = pattern.sub(lambda m: " " * len(m.group(0)), remaining)
    return sorted(found, key=found.get)


def info(name: str) -> Dict:
    return get_dataset().skills.get(name, {"name": name, "category": "Other", "description": "", "how_to_learn": "", "satisfied_by": []})


def covered_by(required: str, have: Set[str]) -> Optional[str]:
    """Return the resume skill that satisfies `required`, if any.

    A generic requirement ("Cloud Platforms") is satisfied by a specific skill
    the resume has ("AWS"); the reverse is not true.
    """
    if required in have:
        return required
    for specific in info(required).get("satisfied_by", []):
        if specific in have:
            return specific
    return None


def related_partial(required: str, have: Set[str]) -> Optional[str]:
    """A resume skill that is a stepping stone toward `required` (partial credit)."""
    for skill in have:
        if required in info(skill).get("satisfied_by", []):
            return skill  # e.g. has "SQL" (generic) toward "PostgreSQL"
    same_family = {
        "Spring Boot": ["Spring", "Java"], "Spring": ["Spring Boot"], "Kubernetes": ["Docker"],
        "Helm": ["Kubernetes"], "Next.js": ["React"], "TypeScript": ["JavaScript"],
        "GCP": ["AWS", "Azure"], "Azure": ["AWS", "GCP"], "AWS": ["GCP", "Azure"],
        "Terraform": ["CloudFormation", "Ansible"], "CloudFormation": ["Terraform"],
        "Vue": ["React", "Angular"], "Angular": ["React", "Vue"], "Go": ["Python", "Java"],
        "Scala": ["Java"], "Kafka": ["Event-Driven Architecture"], "Power BI": ["Tableau"],
        "Tableau": ["Power BI"], "R": ["Python"], "OpenTelemetry": ["Prometheus", "Observability"],
        "Observability": ["Monitoring", "Grafana"], "GitOps": ["CI/CD"], "Distributed Systems": ["Microservices"],
        "Microservices": ["REST APIs", "Spring Boot"], "EDR": ["SIEM"], "CrowdStrike Falcon": ["EDR", "SIEM"],
        "Chronicle": ["SIEM"], "Web Security": ["Security Fundamentals"], "Cloud Security": ["IAM", "AWS"],
        "Design Systems": ["Figma"], "Frontend Architecture": ["React"], "Component Design": ["React", "Design Systems"],
        "Experimentation": ["Statistics"], "Data Pipelines": ["Python", "SQL"], "Data Engineering": ["Data Pipelines", "SQL"],
        "GraphQL": ["REST APIs"], "ClickHouse": ["SQL"], "NoSQL": ["SQL"], "Redis": ["NoSQL"],
        "Hibernate": ["SQL", "Spring Boot"], "Ruby": ["Python"], "Vulnerability Management": ["Security Operations"],
        "CVSS": ["Vulnerability Management"], "OWASP": ["Web Security"], "Machine Learning": ["Statistics"],
    }
    for skill in same_family.get(required, []):
        if skill in have:
            return skill
    return None
