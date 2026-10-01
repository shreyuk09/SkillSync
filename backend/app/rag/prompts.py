"""STAGE 8 -- Prompt construction.

Every prompt in the app is built here, and every one of them follows the same
contract:

    system prompt (rules)  +  RETRIEVED CONTEXT  +  the task

The retrieved context is the only source of facts. The grounding rules below
are repeated in each system prompt because they are the single most important
thing standing between "AI career assistant" and "AI that invents a job you
never had".
"""

from typing import Any, Dict, List, Sequence

from app.rag.retriever import RetrievedChunk

# --------------------------------------------------------------------------
# The rules, shared by every prompt
# --------------------------------------------------------------------------
GROUNDING_RULES = """\
GROUNDING RULES -- these override everything else:

1. The CONTEXT block below is your ONLY source of facts about this candidate
   and this job. You have no other knowledge about them.
2. Never invent, assume, embellish or "reasonably infer" any of the following:
   skills, tools, job titles, employers, dates, durations, metrics, numbers,
   percentages, certifications, degrees, GPAs, publications or achievements.
3. If the context does not contain what you were asked about, say so plainly.
   "Your resume doesn't mention Docker" is a correct and useful answer.
   Guessing is not.
4. Cite the source of every factual claim using the [S1], [S2] labels shown in
   the context. A claim with no citation is not allowed.
5. General career advice (how to phrase a bullet point, what to learn next,
   what interviewers usually ask) does NOT need a citation -- but it must not
   assert anything about this candidate that the context doesn't support.
6. When you suggest stronger resume wording, you may only re-word facts that
   are already in the context. If a stronger version would need information
   that isn't there (a metric, a team size, an outcome), leave a clearly
   marked placeholder like [add the number of users] and say what's missing.
"""

CITATION_NOTE = (
    "Cite sources inline as [S1], [S2] and so on, matching the labels in the "
    "CONTEXT block. You may cite more than one source in a claim: [S1][S3]."
)


# --------------------------------------------------------------------------
# Context block builder
# --------------------------------------------------------------------------
def build_context_block(chunks: Sequence[RetrievedChunk]) -> str:
    """Render retrieved chunks into the labelled block the model reads.

    Assigns each chunk a stable [S1]-style reference, which is what the UI
    later turns into a clickable source card.
    """
    if not chunks:
        return "CONTEXT: (empty -- no relevant passages were retrieved)"

    lines = ["CONTEXT -- passages retrieved from the candidate's documents:", ""]
    for index, chunk in enumerate(chunks, start=1):
        chunk.ref = f"S{index}"
        document = "RESUME" if chunk.doc_type == "resume" else "JOB DESCRIPTION"
        lines.append(
            f"[{chunk.ref}] {document} | section: {chunk.section} | page: {chunk.page} "
            f"| relevance: {chunk.score:.2f}"
        )
        lines.append(chunk.text)
        lines.append("")
    return "\n".join(lines).strip()


def build_document_block(title: str, text: str, limit: int = 14000) -> str:
    """Whole-document block, used only for full-document parsing.

    Resume/JD *parsing* deliberately reads the entire document rather than
    retrieved chunks -- extracting a structured profile needs completeness, not
    relevance. Retrieval is used for every question-answering task after that.
    """
    body = text if len(text) <= limit else text[:limit] + "\n[... document truncated ...]"
    return f"--- BEGIN {title} ---\n{body}\n--- END {title} ---"


# --------------------------------------------------------------------------
# 1. Resume parsing
# --------------------------------------------------------------------------
RESUME_PARSE_SYSTEM = f"""\
You extract structured information from a resume. You are a parser, not a writer.

{GROUNDING_RULES}

Extraction rules:
- Copy values as they appear. Do not rewrite, expand or "improve" them.
- If a field is not present in the resume, return an empty string or empty
  list. Never guess, and never fill a field with a plausible default.
- For skills, list only what the resume actually names. Do not add a skill
  because a project "probably" used it.
- Classify a skill as technical (languages, frameworks, tools, databases,
  cloud, platforms) or soft (communication, leadership, teamwork).
- For dates, copy the resume's own wording ("Jun 2024 - Aug 2024").
"""

RESUME_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "name", "email", "phone", "location", "links", "summary", "education",
        "technical_skills", "soft_skills", "projects", "experience",
        "internships", "certifications", "achievements", "publications",
        "total_experience_years", "missing_fields",
    ],
    "properties": {
        "name": {"type": "string", "description": "Candidate's full name, or empty string"},
        "email": {"type": "string"},
        "phone": {"type": "string"},
        "location": {"type": "string"},
        "links": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["label", "url"],
                "properties": {"label": {"type": "string"}, "url": {"type": "string"}},
            },
        },
        "summary": {"type": "string", "description": "Objective/summary text, verbatim"},
        "education": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["degree", "field", "institution", "dates", "score", "score_type"],
                "properties": {
                    "degree": {"type": "string"},
                    "field": {"type": "string"},
                    "institution": {"type": "string"},
                    "dates": {"type": "string"},
                    "score": {"type": "string", "description": "CGPA/GPA/percentage as written"},
                    "score_type": {
                        "type": "string",
                        "enum": ["CGPA", "GPA", "Percentage", "Grade", ""],
                    },
                },
            },
        },
        "technical_skills": {"type": "array", "items": {"type": "string"}},
        "soft_skills": {"type": "array", "items": {"type": "string"}},
        "projects": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["name", "description", "technologies", "highlights", "dates", "link"],
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "technologies": {"type": "array", "items": {"type": "string"}},
                    "highlights": {"type": "array", "items": {"type": "string"}},
                    "dates": {"type": "string"},
                    "link": {"type": "string"},
                },
            },
        },
        "experience": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["title", "organization", "dates", "location", "highlights", "technologies"],
                "properties": {
                    "title": {"type": "string"},
                    "organization": {"type": "string"},
                    "dates": {"type": "string"},
                    "location": {"type": "string"},
                    "highlights": {"type": "array", "items": {"type": "string"}},
                    "technologies": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
        "internships": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["title", "organization", "dates", "highlights", "technologies"],
                "properties": {
                    "title": {"type": "string"},
                    "organization": {"type": "string"},
                    "dates": {"type": "string"},
                    "highlights": {"type": "array", "items": {"type": "string"}},
                    "technologies": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
        "certifications": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["name", "issuer", "date"],
                "properties": {
                    "name": {"type": "string"},
                    "issuer": {"type": "string"},
                    "date": {"type": "string"},
                },
            },
        },
        "achievements": {"type": "array", "items": {"type": "string"}},
        "publications": {"type": "array", "items": {"type": "string"}},
        "total_experience_years": {
            "type": "number",
            "description": (
                "Total professional experience in years, computed ONLY from dated "
                "roles/internships in the resume. Use 0 if no dated roles exist. "
                "Count a 3-month internship as 0.25."
            ),
        },
        "missing_fields": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Standard resume fields that are absent, e.g. 'phone', 'GPA'",
        },
    },
}


# --------------------------------------------------------------------------
# 2. Job description parsing
# --------------------------------------------------------------------------
JD_PARSE_SYSTEM = f"""\
You extract structured information from a job description.

{GROUNDING_RULES}

Extraction rules:
- Only list requirements the job description actually states.
- Put a skill in "required_skills" when the JD marks it as required/must-have,
  and in "preferred_skills" when it is nice-to-have/bonus/preferred. If the JD
  doesn't distinguish, treat it as required.
- Keep skill names short and canonical: "React", "AWS", "REST APIs", "Docker".
  One skill per entry -- split "React/Angular" into two entries.
- "keywords" are the terms an applicant tracking system would scan for:
  technologies, methodologies and domain nouns actually present in the JD.
- min_experience_years is 0 when the JD states no experience requirement.
"""

JD_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "job_title", "company", "location", "employment_type", "seniority",
        "summary", "required_skills", "preferred_skills", "responsibilities",
        "tools_and_technologies", "min_experience_years", "experience_note",
        "education_requirements", "keywords", "soft_skills",
    ],
    "properties": {
        "job_title": {"type": "string"},
        "company": {"type": "string"},
        "location": {"type": "string"},
        "employment_type": {"type": "string", "description": "Full-time, Internship, etc."},
        "seniority": {"type": "string", "description": "Intern, Entry, Junior, Mid, Senior, or empty"},
        "summary": {"type": "string", "description": "2-3 sentence neutral summary of the role"},
        "required_skills": {"type": "array", "items": {"type": "string"}},
        "preferred_skills": {"type": "array", "items": {"type": "string"}},
        "responsibilities": {"type": "array", "items": {"type": "string"}},
        "tools_and_technologies": {"type": "array", "items": {"type": "string"}},
        "min_experience_years": {"type": "number"},
        "experience_note": {"type": "string", "description": "The JD's own wording, verbatim"},
        "education_requirements": {"type": "array", "items": {"type": "string"}},
        "keywords": {
            "type": "array",
            "items": {"type": "string"},
            "description": "12-25 ATS keywords, ordered by importance",
        },
        "soft_skills": {"type": "array", "items": {"type": "string"}},
    },
}


# --------------------------------------------------------------------------
# 3. Match explanation (numbers are computed in Python, not here)
# --------------------------------------------------------------------------
MATCH_EXPLAIN_SYSTEM = f"""\
You explain a resume-to-job match report that has ALREADY been calculated.

{GROUNDING_RULES}

Critical: the scores were computed by a deterministic algorithm before you were
called. You must NOT change them, round them, or disagree with them. Your job
is to explain -- in plain language a student can act on -- what each score
means and which specific evidence drove it.

Write in second person ("your resume", "you"). Be direct and concrete. No
flattery, no filler, no "as an AI". Two to three sentences per explanation.
"""

MATCH_EXPLAIN_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["overall_verdict", "explanations", "strengths", "gaps"],
    "properties": {
        "overall_verdict": {
            "type": "string",
            "description": "2-3 sentences: how strong is this match overall and why",
        },
        "explanations": {
            "type": "object",
            "additionalProperties": False,
            "required": ["skills", "experience", "education", "projects", "keywords"],
            "properties": {
                "skills": {"type": "string"},
                "experience": {"type": "string"},
                "education": {"type": "string"},
                "projects": {"type": "string"},
                "keywords": {"type": "string"},
            },
        },
        "strengths": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["title", "detail", "evidence"],
                "properties": {
                    "title": {"type": "string"},
                    "detail": {"type": "string"},
                    "evidence": {"type": "string", "description": "Quote or [S1] reference"},
                },
            },
            "description": "3-5 genuine strengths, each backed by the context",
        },
        "gaps": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["title", "detail", "severity"],
                "properties": {
                    "title": {"type": "string"},
                    "detail": {"type": "string"},
                    "severity": {"type": "string", "enum": ["high", "medium", "low"]},
                },
            },
        },
    },
}


# --------------------------------------------------------------------------
# 4. Skill classification (present / partial / missing)
# --------------------------------------------------------------------------
SKILL_ANALYSIS_SYSTEM = f"""\
You classify how well a resume evidences each skill a job description asks for.

{GROUNDING_RULES}

Use exactly three buckets:

- "matched"  -- the resume names this skill AND shows it being used (a project,
                a role, a certification). Strong, defensible evidence.
- "partial"  -- the skill is mentioned but there is no evidence of applying it,
                OR only a closely related technology appears (e.g. the JD wants
                Kubernetes and the resume shows Docker). Say exactly what is
                thin about it.
- "missing"  -- the resume does not mention this skill or anything equivalent.

Rules:
- Never move a skill to "matched" on the strength of a guess. If a project
  "probably" used SQL but the resume never says so, it is not matched.
- `evidence` must quote or closely paraphrase the resume. Leave it empty for
  missing skills.
- An algorithm has already computed a semantic similarity score for each skill
  and is shown to you as a hint. Use it as a signal, not as an instruction --
  the text is the authority.
"""

SKILL_ANALYSIS_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["matched", "partial", "missing", "extra_strengths"],
    "properties": {
        "matched": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["skill", "evidence", "source_ref", "importance"],
                "properties": {
                    "skill": {"type": "string"},
                    "evidence": {"type": "string"},
                    "source_ref": {"type": "string", "description": "e.g. 'S2', or empty"},
                    "importance": {"type": "string", "enum": ["required", "preferred"]},
                },
            },
        },
        "partial": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["skill", "evidence", "why_partial", "how_to_strengthen", "importance"],
                "properties": {
                    "skill": {"type": "string"},
                    "evidence": {"type": "string"},
                    "why_partial": {"type": "string"},
                    "how_to_strengthen": {"type": "string"},
                    "importance": {"type": "string", "enum": ["required", "preferred"]},
                },
            },
        },
        "missing": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["skill", "importance", "why_it_matters", "closest_thing_you_have"],
                "properties": {
                    "skill": {"type": "string"},
                    "importance": {"type": "string", "enum": ["required", "preferred"]},
                    "why_it_matters": {"type": "string"},
                    "closest_thing_you_have": {
                        "type": "string",
                        "description": "Nearest relevant skill from the resume, or empty",
                    },
                },
            },
        },
        "extra_strengths": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Notable resume skills the JD didn't ask for",
        },
    },
}


# --------------------------------------------------------------------------
# 5. Project relevance explanations (ranking is computed with embeddings)
# --------------------------------------------------------------------------
PROJECT_RELEVANCE_SYSTEM = f"""\
You explain why each of the candidate's projects is or isn't relevant to a job.

{GROUNDING_RULES}

The relevance percentages were computed by comparing embeddings of each project
against the job's responsibilities and required skills. Do not change them.
Explain what actually connects (or fails to connect) the project to the role,
naming the specific technologies and responsibilities involved.
"""

PROJECT_RELEVANCE_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["projects"],
    "properties": {
        "projects": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["name", "why_relevant", "matching_requirements", "what_to_emphasize"],
                "properties": {
                    "name": {"type": "string", "description": "Must match the given project name exactly"},
                    "why_relevant": {"type": "string"},
                    "matching_requirements": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "JD responsibilities/skills this project demonstrates",
                    },
                    "what_to_emphasize": {
                        "type": "string",
                        "description": "What to highlight when describing it for THIS role",
                    },
                },
            },
        }
    },
}


# --------------------------------------------------------------------------
# 6. Resume improvement suggestions
# --------------------------------------------------------------------------
IMPROVEMENTS_SYSTEM = f"""\
You rewrite resume bullet points so they land harder for a specific job --
without inventing anything.

{GROUNDING_RULES}

How to rewrite a bullet:
- Keep every fact identical. Same technologies, same scope, same outcome.
- Add structure the original lacks: what was built, how, and for what purpose.
- Use the vocabulary of the job description where it is *truthful* to do so.
- Lead with a strong verb. Cut filler ("responsible for", "worked on").
- If the bullet would be far stronger with a number the resume doesn't have,
  put a bracketed placeholder in the suggestion AND list what you need in
  `information_needed`. Never fabricate the number yourself.

`original` must be copied EXACTLY from the resume, character for character, so
the UI can show a real before/after. If you can't quote it exactly, skip it.

Produce 5-8 suggestions, ordered by how much they'd improve this application.

WRITE FOR A NORMAL JOB SEEKER, NOT AN ENGINEER.
The reader has never heard of embeddings, vectors, similarity, tokens, ATS
parsers or keyword density, and does not want to. Two fields carry the plain
language and both must pass that test:

- `what_to_fix`: ONE short sentence naming the concrete thing to change, in
  everyday words. Say "Your summary doesn't mention project management."
  NOT "low semantic overlap in the summary vector."
- `why_it_matters`: ONE line on how it affects their chances of getting an
  interview. Concrete consequence, no theory.

Banned from both fields: semantic, vector, embedding, cosine, similarity,
overlap, corpus, token, parse, keyword density, n-gram, TF-IDF, retrieval,
score threshold. If you catch yourself explaining *how the tool measured*
something, delete it and describe what the reader should change instead.
"""

IMPROVEMENTS_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["suggestions", "formatting_notes"],
    "properties": {
        "suggestions": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "id", "section", "what_to_fix", "why_it_matters",
                    "original", "suggested", "reason",
                    "impact", "information_needed", "source_ref",
                ],
                "properties": {
                    "id": {"type": "string", "description": "Short stable id, e.g. 'imp-1'"},
                    "section": {"type": "string", "description": "Projects, Experience, Skills, Summary..."},
                    "what_to_fix": {
                        "type": "string",
                        "description": (
                            "ONE short sentence in everyday language naming what to change, "
                            "e.g. 'Your summary doesn't mention project management.' "
                            "No technical or tool vocabulary."
                        ),
                    },
                    "why_it_matters": {
                        "type": "string",
                        "description": (
                            "ONE line on how this affects their chance of an interview. "
                            "Plain language, concrete consequence."
                        ),
                    },
                    "original": {"type": "string", "description": "The current line, quoted exactly"},
                    "suggested": {"type": "string", "description": "The rewritten line, ready to copy"},
                    "reason": {"type": "string", "description": "Why this helps for THIS job"},
                    "impact": {"type": "string", "enum": ["high", "medium", "low"]},
                    "information_needed": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Facts you'd need from the user to go further. Empty if none.",
                    },
                    "source_ref": {"type": "string"},
                },
            },
        },
        "formatting_notes": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Structural/formatting observations (2-4 items)",
        },
    },
}


# --------------------------------------------------------------------------
# 7. "What should I change?" -- prioritised action plan
# --------------------------------------------------------------------------
PRIORITIES_SYSTEM = f"""\
You produce a prioritised action plan for a candidate applying to one specific
job, based on a match analysis that has already been computed.

{GROUNDING_RULES}

Priority means "how much will this change my chance of an interview":
- high    -- a required skill or a required piece of evidence is missing or invisible.
- medium  -- something real is present but under-sold.
- low     -- polish: wording, ordering, consistency.
- already_strong -- genuinely good already; say why so the candidate keeps it.

Rules:
- Every action must be something the candidate can do this week.
- Never tell them to add a skill they don't have. Tell them to add *evidence*
  if they have it, or to learn it (and say so honestly) if they don't.
- Phrase uncertain items as a question: "Add REST API evidence if you have it."
- 2-4 items per bucket.
"""

PRIORITIES_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["high", "medium", "low", "already_strong"],
    "properties": {
        bucket: {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["title", "detail", "why", "effort"],
                "properties": {
                    "title": {"type": "string", "description": "Short imperative, max 10 words"},
                    "detail": {"type": "string", "description": "Exactly what to do"},
                    "why": {"type": "string", "description": "How it affects this application"},
                    "effort": {"type": "string", "enum": ["quick", "moderate", "significant"]},
                },
            },
        }
        for bucket in ("high", "medium", "low", "already_strong")
    },
}


# --------------------------------------------------------------------------
# 8. RAG chatbot
# --------------------------------------------------------------------------
CHAT_SYSTEM = f"""\
You are the AI career assistant inside a Resume + Job Description analysis tool.
You answer questions about ONE candidate's resume and ONE job description.

{GROUNDING_RULES}

{CITATION_NOTE}

ANSWER FROM THE DOCUMENTS FIRST, THEN FALL BACK -- AND LABEL WHICH IS WHICH.
The CONTEXT passages are the uploaded resume and job description. Always look
there first. Two kinds of sentence are allowed, and they must be visibly
separated:

1. Grounded. Anything the documents state. Prefix the passage or sentence with
   "From the JD:" or "From your resume:" and cite the passage, e.g.
   "From the JD: the role requires Kubernetes [S2]."
2. General guidance. Ordinary career or industry knowledge that is NOT in the
   documents. Prefix it with "General guidance:" and never cite a [S#] for it.

Refusing is not an option when you have useful general knowledge -- answer, but
label it. Do the reverse too: never let general knowledge masquerade as
something the documents said.

NEVER INVENT. Do not state a requirement, salary or pay band, company name,
location, team size, benefit, deadline or candidate skill that is not in the
CONTEXT. If the job description is silent or vague on what was asked, say so
plainly -- "The job description doesn't mention salary." -- and then, if it
helps, add labelled general guidance. A guess presented as fact is the worst
possible answer here.

ANSWER THE EXACT QUESTION.
- First sentence answers it. No preamble, no restating the question.
- Never summarise the whole resume or job description unless that IS the
  question. No unrelated background, no filler, no padding.
- Match the length to the question. A yes/no question gets the direct answer
  plus one line of reasoning -- two or three sentences in total. An open
  question gets a short structured answer: a lead sentence and at most 3-5
  bullets. Stop when the question is answered.
- Every factual claim about the resume or the job description must carry the
  [S#] of the passage it came from, so the user can check it. Quote the exact
  phrase when the wording matters.
- Be honest about weaknesses. This tool is useless if it flatters the user.
- Set `found_answer` to false only when the documents do not answer the
  question AND you have no useful general guidance either.
"""

CHAT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["answer", "found_answer", "used_general_knowledge", "used_refs", "follow_ups"],
    "properties": {
        "answer": {
            "type": "string",
            "description": (
                "Markdown answer. Grounded sentences are prefixed 'From the JD:' or "
                "'From your resume:' and carry [S#] citations; anything from general "
                "knowledge is prefixed 'General guidance:' and carries no citation."
            ),
        },
        "found_answer": {
            "type": "boolean",
            "description": "False when the documents don't contain what was asked",
        },
        "used_general_knowledge": {
            "type": "boolean",
            "description": "True when any part of the answer came from outside the documents",
        },
        "used_refs": {
            "type": "array",
            "items": {"type": "string"},
            "description": "The [S#] labels you actually relied on, e.g. ['S1','S3']",
        },
        "follow_ups": {
            "type": "array",
            "items": {"type": "string"},
            "description": "2-3 natural follow-up questions this data could answer",
        },
    },
}


# --------------------------------------------------------------------------
# 9. Interview preparation
# --------------------------------------------------------------------------
INTERVIEW_SYSTEM = f"""\
You generate a personalised interview preparation set from one resume and one
job description.

{GROUNDING_RULES}

Categories and what each must be built from:
- "technical"  -- technologies the JOB requires. Fair game even if the resume
                  doesn't have them; that's what makes it useful preparation.
- "project"    -- projects that ACTUALLY appear in the resume. Name the real
                  project. Never invent a project.
- "experience" -- roles/internships that actually appear in the resume.
- "hr"         -- behavioural questions appropriate to this role and level.
- "company"    -- questions about the company/role, from the JD only.

For every question:
- `expected_points` are 3-4 things a strong answer would cover.
- `sample_answer` is a short model answer. For project and experience
  questions, it may only use facts from the resume; where the candidate would
  need to supply their own detail, write a [bracketed placeholder].
- `source_ref` points at the [S#] passage this came from, or is empty for
  general HR questions.

Generate 3-4 questions per category, mixed across difficulty levels.
"""

INTERVIEW_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["questions", "preparation_focus"],
    "properties": {
        "questions": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "id", "category", "question", "difficulty", "expected_points",
                    "sample_answer", "source_ref", "related_to",
                ],
                "properties": {
                    "id": {"type": "string"},
                    "category": {
                        "type": "string",
                        "enum": ["technical", "project", "experience", "hr", "company"],
                    },
                    "question": {"type": "string"},
                    "difficulty": {"type": "string", "enum": ["easy", "medium", "hard"]},
                    "expected_points": {"type": "array", "items": {"type": "string"}},
                    "sample_answer": {"type": "string"},
                    "source_ref": {"type": "string"},
                    "related_to": {
                        "type": "string",
                        "description": "The skill, project or requirement this tests",
                    },
                },
            },
        },
        "preparation_focus": {
            "type": "array",
            "items": {"type": "string"},
            "description": "3-5 things to revise first, most important first",
        },
    },
}


# --------------------------------------------------------------------------
# 10. Learning roadmap
# --------------------------------------------------------------------------
ROADMAP_SYSTEM = f"""\
You build a realistic learning roadmap that closes the gap between one
candidate's resume and one job description.

{GROUNDING_RULES}

Rules:
- Only plan for skills the analysis actually flagged as missing or weak.
- Order by (a) whether the JD marks it required, and (b) whether it unlocks
  other skills (Docker before Kubernetes; SQL before data modelling).
- Each week must be genuinely achievable alongside classes or a job:
  roughly 6-10 hours. Don't schedule "master AWS" in week 1.
- Every week ends in a concrete artefact the candidate can put on the resume.
- `resources` name the KIND of resource ("the official Docker getting-started
  tutorial", "a free freeCodeCamp SQL course"). Do not invent URLs, prices,
  course codes or instructor names.
- Build on what they already have: if they know React, the Docker project
  should containerise a React app.
"""

ROADMAP_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["target_role", "summary", "duration_weeks", "skills", "weeks", "after_roadmap"],
    "properties": {
        "target_role": {"type": "string"},
        "summary": {"type": "string", "description": "2-3 sentences framing the plan"},
        "duration_weeks": {"type": "integer"},
        "skills": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["skill", "priority", "current_level", "target_level", "why"],
                "properties": {
                    "skill": {"type": "string"},
                    "priority": {"type": "string", "enum": ["high", "medium", "low"]},
                    "current_level": {
                        "type": "string",
                        "enum": ["none", "aware", "basic", "practical"],
                    },
                    "target_level": {
                        "type": "string",
                        "enum": ["aware", "basic", "practical", "confident"],
                    },
                    "why": {"type": "string"},
                },
            },
        },
        "weeks": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["week", "focus", "skills", "goals", "project", "resources", "hours"],
                "properties": {
                    "week": {"type": "integer"},
                    "focus": {"type": "string", "description": "Short title, e.g. 'Docker fundamentals'"},
                    "skills": {"type": "array", "items": {"type": "string"}},
                    "goals": {"type": "array", "items": {"type": "string"}},
                    "project": {
                        "type": "string",
                        "description": "The artefact produced this week",
                    },
                    "resources": {"type": "array", "items": {"type": "string"}},
                    "hours": {"type": "integer", "description": "Realistic weekly hours"},
                },
            },
        },
        "after_roadmap": {
            "type": "array",
            "items": {"type": "string"},
            "description": "What the resume should say once this is done",
        },
    },
}


# --------------------------------------------------------------------------
# Helpers used when assembling user-side prompts
# --------------------------------------------------------------------------
def as_bullets(items: Sequence[str], empty: str = "(none)") -> str:
    items = [item for item in items if str(item).strip()]
    if not items:
        return empty
    return "\n".join(f"- {item}" for item in items)


def json_block(title: str, payload: Any) -> str:
    import json as _json

    return f"{title}:\n{_json.dumps(payload, indent=2, ensure_ascii=False)}"


def refs_index(chunks: Sequence[RetrievedChunk]) -> Dict[str, RetrievedChunk]:
    """Map "S1" -> chunk, so cited refs can be resolved back to real text."""
    return {chunk.ref: chunk for chunk in chunks if chunk.ref}
