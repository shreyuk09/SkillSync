"""Deterministic skill matching -- the evidence layer under every score.

A skill from the job description is classified against the resume using two
independent signals:

1. **Lexical evidence** -- does the skill (or a known alias) literally appear,
   and *where*? A skill named in a project or a job is evidence of use. A skill
   that appears only in the "Skills" list is a claim, not evidence. That
   distinction is exactly what "partially matched" means in this app.

2. **Semantic evidence** -- the embedding of "Experience with Kubernetes"
   compared against every resume chunk. This catches related work the words
   miss: someone who wrote "deployed containerised services with Docker
   Compose" gets partial credit toward Kubernetes even though the word never
   appears.

Neither signal ever *invents* a skill: a skill with no lexical hit and weak
similarity is reported as missing, full stop.
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Set

from app.rag.retriever import Retriever

# Sections that count as "evidence of applying the skill" rather than
# "claiming the skill".
EVIDENCE_SECTIONS = {"projects", "experience", "internships", "certifications", "achievements", "publications"}
CLAIM_SECTIONS = {"skills", "summary", "contact", "interests", "languages"}

# Similarity calibration. Cosine values sit in completely different ranges
# depending on the embedder, so each provider gets its own numbers.
#
# `related`  -- absolute similarity a passage must reach to count as related work.
# `margin`   -- how far it must also stand ABOVE that document's average
#               similarity to the same query. Without this second test, a model
#               that scores everything around 0.3 would mark every skill as
#               "related" (which is exactly what the hashing embedder does).
#
# The neural numbers are measured, not guessed. Against this project's sample
# resume, "Experience and hands-on work with X" scores:
#     Java 0.55, Spring Boot 0.50   (genuinely present)
#     Kubernetes 0.32, AWS 0.29, Docker 0.25   (genuinely absent)
#     an unrelated skill 0.09
# so 0.40 cleanly separates present from absent.
THRESHOLDS = {
    True: {"related": 0.40, "margin": 0.10},   # neural embeddings
    False: {"related": 0.99, "margin": 0.99},  # hashing fallback: never infer
}

# Raw cosine ranges differ per *comparison type*, not just per model, so each
# gets its own (floor, ceiling) rescaling window.
#
#   "skill"       -- a short skill query against a resume passage.
#   "requirement" -- a project or resume passage against a job requirement.
#                    Measured range: 0.02 for unrelated text, 0.26-0.30 for a
#                    strongly on-topic project. Anything above 0.30 is a
#                    near-restatement, so that's the ceiling.
CALIBRATION = {
    "skill": {True: (0.15, 0.55), False: (0.05, 0.45)},
    "requirement": {True: (0.05, 0.34), False: (0.15, 0.45)},
}

# Common ways the same technology gets written. Keeps "ReactJS" and "React"
# from being treated as two different skills.
SKILL_ALIASES: Dict[str, List[str]] = {
    "javascript": ["js", "es6", "ecmascript", "vanilla js"],
    "typescript": ["ts"],
    "react": ["reactjs", "react.js", "react js"],
    "angular": ["angularjs", "angular.js"],
    "vue": ["vuejs", "vue.js"],
    "node.js": ["node", "nodejs", "node js"],
    "express": ["expressjs", "express.js"],
    "python": ["python3", "py"],
    "java": ["core java", "java se", "java 8", "java 11", "java 17"],
    "c++": ["cpp", "c plus plus"],
    "c#": ["csharp", "c sharp", ".net c#"],
    ".net": ["dotnet", "asp.net", "dot net"],
    "sql": ["mysql", "postgresql", "postgres", "sqlite", "ms sql", "sql server",
            "plsql", "pl/sql", "t-sql", "oracle sql"],
    "nosql": ["mongodb", "mongo", "cassandra", "dynamodb", "couchdb"],
    "rest apis": ["rest", "restful", "rest api", "restful api", "restful apis",
                  "rest services", "web api", "api development"],
    "graphql": ["graph ql"],
    "aws": ["amazon web services", "ec2", "s3", "lambda", "amazon aws"],
    "azure": ["microsoft azure", "azure cloud"],
    "gcp": ["google cloud", "google cloud platform"],
    "docker": ["containerization", "containerisation", "containers", "docker compose"],
    "kubernetes": ["k8s", "kubectl", "eks", "aks", "gke"],
    "ci/cd": ["cicd", "continuous integration", "continuous deployment",
              "continuous delivery", "jenkins", "github actions", "gitlab ci"],
    "git": ["github", "gitlab", "bitbucket", "version control"],
    "machine learning": ["ml", "supervised learning", "scikit-learn", "sklearn"],
    "deep learning": ["dl", "neural networks", "cnn", "rnn", "transformers"],
    "tensorflow": ["tf", "keras"],
    "pytorch": ["torch"],
    "data analysis": ["data analytics", "analytics", "exploratory data analysis", "eda"],
    "pandas": ["pandas library"],
    "numpy": ["numerical python"],
    "power bi": ["powerbi", "microsoft power bi"],
    "tableau": ["tableau desktop"],
    "excel": ["ms excel", "microsoft excel", "spreadsheets", "advanced excel"],
    "html": ["html5"],
    "css": ["css3", "scss", "sass", "less"],
    "tailwind css": ["tailwind", "tailwindcss"],
    "bootstrap": ["bootstrap 5", "bootstrap4"],
    "next.js": ["nextjs", "next js"],
    "django": ["django rest framework", "drf"],
    "flask": ["flask api"],
    "fastapi": ["fast api"],
    "spring boot": ["spring", "springboot", "spring mvc"],
    "linux": ["unix", "bash", "shell scripting", "ubuntu"],
    "agile": ["scrum", "kanban", "agile methodology", "sprint"],
    "testing": ["unit testing", "junit", "pytest", "jest", "test automation", "tdd"],
    "microservices": ["micro services", "microservice architecture"],
    "data structures": ["dsa", "data structures and algorithms", "algorithms"],
    "oop": ["object oriented programming", "object-oriented", "oops"],
    "figma": ["figma design"],
    "redux": ["redux toolkit"],
    "firebase": ["firestore"],
    "redis": ["redis cache"],
    "kafka": ["apache kafka"],
    "spark": ["apache spark", "pyspark"],
    "airflow": ["apache airflow"],
    "etl": ["extract transform load", "data pipeline", "data pipelines"],
    "statistics": ["statistical analysis", "hypothesis testing", "a/b testing"],
}

# Reverse index: any known variant -> canonical name.
_VARIANT_TO_CANONICAL: Dict[str, str] = {}
for _canonical, _variants in SKILL_ALIASES.items():
    _VARIANT_TO_CANONICAL[_canonical] = _canonical
    for _variant in _variants:
        _VARIANT_TO_CANONICAL[_variant] = _canonical


def canonical_skill(skill: str) -> str:
    key = re.sub(r"\s+", " ", skill.strip().lower())
    return _VARIANT_TO_CANONICAL.get(key, key)


def skill_variants(skill: str) -> List[str]:
    """Every string that should count as a mention of this skill."""
    canonical = canonical_skill(skill)
    variants = {canonical, skill.strip().lower()}
    variants.update(SKILL_ALIASES.get(canonical, []))
    return [variant for variant in variants if variant]


def _pattern_for(variant: str) -> re.Pattern:
    """Word-boundary regex that survives punctuation like c++, .net, node.js."""
    escaped = re.escape(variant)
    # \b doesn't work after a symbol, so guard with "not a word character".
    prefix = r"(?<![A-Za-z0-9])"
    suffix = r"(?![A-Za-z0-9])" if variant[-1].isalnum() else ""
    return re.compile(prefix + escaped + suffix, re.IGNORECASE)


_PATTERN_CACHE: Dict[str, re.Pattern] = {}


def mentions(text: str, skill: str) -> bool:
    for variant in skill_variants(skill):
        pattern = _PATTERN_CACHE.get(variant)
        if pattern is None:
            pattern = _PATTERN_CACHE[variant] = _pattern_for(variant)
        if pattern.search(text):
            return True
    return False


def count_mentions(text: str, skill: str) -> int:
    total = 0
    for variant in skill_variants(skill):
        pattern = _PATTERN_CACHE.get(variant)
        if pattern is None:
            pattern = _PATTERN_CACHE[variant] = _pattern_for(variant)
        total += len(pattern.findall(text))
    return total


@dataclass
class SkillMatch:
    """The full evidence trail for one job-description skill."""

    skill: str
    importance: str  # "required" | "preferred"
    status: str  # "matched" | "partial" | "missing"
    reason: str  # plain-English explanation of the classification
    lexical_hit: bool = False
    evidence_sections: List[str] = field(default_factory=list)
    semantic_score: float = 0.0
    alignment: float = 0.0  # semantic score normalised to 0..1
    evidence_text: str = ""
    evidence_citation: str = ""
    evidence_chunk_id: str = ""
    mention_count: int = 0

    @property
    def credit(self) -> float:
        """How much this skill contributes to the skills score."""
        return {"matched": 1.0, "partial": 0.5, "missing": 0.0}[self.status]

    @property
    def weight(self) -> float:
        return 1.0 if self.importance == "required" else 0.4


def normalize_alignment(score: float, is_semantic: bool, kind: str = "skill") -> float:
    """Map a raw cosine similarity onto an interpretable 0..1 'alignment'.

    Raw cosine values are not intuitive: 0.26 sounds low but is a strong match
    between a project and a job requirement, while 0.26 between a skill query
    and a resume passage means the skill isn't there. We linearly rescale
    between a floor (below which text is unrelated) and a ceiling (above which
    it's clearly on-topic), calibrated per embedder and per comparison type.
    """
    floor, ceiling = CALIBRATION.get(kind, CALIBRATION["skill"])[is_semantic]
    if ceiling <= floor:
        return 0.0
    return max(0.0, min(1.0, (score - floor) / (ceiling - floor)))


def classify_skill(
    skill: str,
    importance: str,
    *,
    session_id: str,
    retriever: Retriever,
    resume_text: str,
    chunks_by_section: Dict[str, List[dict]],
) -> SkillMatch:
    """Classify one JD skill against the resume. No LLM involved."""
    is_semantic = bool(retriever.embedder_info.get("semantic"))
    bounds = THRESHOLDS[is_semantic]

    lexical_hit = mentions(resume_text, skill)
    mention_count = count_mentions(resume_text, skill) if lexical_hit else 0

    # Where does the skill actually appear?
    evidence_sections: List[str] = []
    for section, chunks in chunks_by_section.items():
        if any(mentions(chunk["text"], skill) for chunk in chunks):
            evidence_sections.append(section)

    has_practical_evidence = any(
        section.lower() in EVIDENCE_SECTIONS for section in evidence_sections
    )

    # Semantic check -- how strongly does the resume support this skill, and
    # does any one passage really stand out from the rest of the document?
    query = f"Experience and hands-on work with {skill}"
    profile = retriever.similarity_profile(session_id, query, doc_type="resume")
    best = profile["best_hit"]
    semantic_score = profile["best"]
    margin = profile["margin"]
    alignment = normalize_alignment(semantic_score, is_semantic)

    # Both tests must pass. The hashing embedder can't detect synonyms at all,
    # so its thresholds are set unreachably high: with no lexical hit it reports
    # "missing", which is the honest answer for a model that cannot know better.
    semantically_related = (
        semantic_score >= bounds["related"] and margin >= bounds["margin"]
    )

    # ---- classification ------------------------------------------------
    if lexical_hit and has_practical_evidence:
        status = "matched"
        where = ", ".join(sorted(evidence_sections))
        reason = f"Named in your resume and demonstrated in: {where}."
    elif lexical_hit:
        status = "partial"
        where = ", ".join(sorted(evidence_sections)) or "your skills list"
        reason = (
            f"Listed in {where}, but no project or role in your resume shows you using it."
        )
    elif semantically_related:
        status = "partial"
        reason = (
            "Not named anywhere in your resume, but closely related work was found "
            f"(similarity {semantic_score:.2f}, which is {margin:.2f} above the rest "
            "of your resume)."
        )
    else:
        status = "missing"
        reason = "No mention of this skill, and nothing closely related, in your resume."

    return SkillMatch(
        skill=skill,
        importance=importance,
        status=status,
        reason=reason,
        lexical_hit=lexical_hit,
        evidence_sections=sorted(evidence_sections),
        semantic_score=round(semantic_score, 4),
        alignment=round(alignment, 4),
        evidence_text=best.text if (best and status != "missing") else "",
        evidence_citation=best.citation if (best and status != "missing") else "",
        evidence_chunk_id=best.chunk_id if (best and status != "missing") else "",
        mention_count=mention_count,
    )


def classify_all(
    required: Sequence[str],
    preferred: Sequence[str],
    *,
    session_id: str,
    retriever: Retriever,
    resume_text: str,
    resume_chunks: Sequence[dict],
) -> List[SkillMatch]:
    """Classify every JD skill, de-duplicating aliases across both lists."""
    chunks_by_section: Dict[str, List[dict]] = {}
    for chunk in resume_chunks:
        chunks_by_section.setdefault(chunk["section"], []).append(chunk)

    seen: Set[str] = set()
    results: List[SkillMatch] = []

    for skills, importance in ((required, "required"), (preferred, "preferred")):
        for skill in skills:
            skill = str(skill).strip()
            if not skill:
                continue
            key = canonical_skill(skill)
            if key in seen:
                continue
            seen.add(key)
            results.append(
                classify_skill(
                    skill,
                    importance,
                    session_id=session_id,
                    retriever=retriever,
                    resume_text=resume_text,
                    chunks_by_section=chunks_by_section,
                )
            )

    return results


def extra_resume_skills(
    resume_skills: Sequence[str], jd_skills: Sequence[str]
) -> List[str]:
    """Resume skills the job description never asked for."""
    wanted = {canonical_skill(skill) for skill in jd_skills}
    extras: List[str] = []
    seen: Set[str] = set()
    for skill in resume_skills:
        key = canonical_skill(skill)
        if key not in wanted and key not in seen:
            seen.add(key)
            extras.append(skill)
    return extras
