"""STAGE 3 -- Section detection.

Resumes and job descriptions are not free-form prose; they are a sequence of
labelled blocks. Detecting those blocks buys us three things:

1. **Better citations.** "Resume -> Projects -> Page 1" instead of "chunk #7".
2. **Better chunks.** We never let a chunk straddle two sections, so a chunk
   is always about one coherent topic.
3. **Filtered retrieval.** The match scorer can ask for *only* the JD's
   "Required skills" section, or *only* the resume's projects.

The detector is heuristic (no LLM call) so ingestion stays fast and free.
"""

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

# --------------------------------------------------------------------------
# Canonical section names + the headings that map onto them
# --------------------------------------------------------------------------
RESUME_SECTIONS: Dict[str, List[str]] = {
    "Contact": ["contact", "contact information", "personal details", "personal information"],
    "Summary": ["summary", "objective", "profile", "career objective", "about me",
                "professional summary", "career summary"],
    "Education": ["education", "academic background", "academics", "qualifications",
                  "educational qualifications", "academic qualifications"],
    "Skills": ["skills", "technical skills", "core competencies", "technologies",
               "technical proficiencies", "areas of expertise", "tech stack",
               "programming languages", "tools and technologies", "soft skills"],
    "Experience": ["experience", "work experience", "professional experience",
                   "employment", "employment history", "work history", "career history"],
    "Internships": ["internship", "internships", "internship experience", "training"],
    "Projects": ["projects", "academic projects", "personal projects", "key projects",
                 "project work", "selected projects", "major projects", "mini projects"],
    "Certifications": ["certifications", "certification", "courses", "licenses",
                       "certificates", "online courses"],
    "Achievements": ["achievements", "awards", "honors", "honours", "accomplishments",
                     "awards and achievements", "extracurricular", "activities",
                     "positions of responsibility", "leadership"],
    "Publications": ["publications", "papers", "research", "research papers",
                     "conferences", "patents"],
    "Languages": ["languages", "languages known"],
    "Interests": ["interests", "hobbies", "hobbies and interests"],
}

JD_SECTIONS: Dict[str, List[str]] = {
    "About": ["about", "about us", "about the company", "company", "overview",
              "job summary", "role overview", "the role", "job description",
              "position summary", "who we are"],
    "Responsibilities": ["responsibilities", "key responsibilities", "duties",
                         "what you will do", "what you'll do", "your role",
                         "job responsibilities", "day to day", "role and responsibilities"],
    "Requirements": ["requirements", "required", "required skills", "must have",
                     "must haves", "minimum qualifications", "basic qualifications",
                     "what we are looking for", "what we're looking for",
                     "required qualifications", "eligibility", "who you are",
                     "essential skills", "mandatory skills"],
    "Preferred": ["preferred", "preferred skills", "nice to have", "nice to haves",
                  "good to have", "bonus points", "desired skills", "plus points",
                  "preferred qualifications", "additional skills"],
    "Skills": ["skills", "technical skills", "technologies", "tech stack",
               "tools and technologies", "technical requirements"],
    "Education": ["education", "educational requirements", "academic requirements",
                  "qualification", "degree requirements"],
    "Experience": ["experience", "experience required", "experience requirements",
                   "years of experience"],
    "Benefits": ["benefits", "perks", "what we offer", "compensation", "salary",
                 "why join us", "we offer"],
}

DEFAULT_SECTION = {"resume": "Summary", "jd": "About"}

# A heading is short, has few words, and doesn't end like a sentence.
_MAX_HEADING_LEN = 64
_MAX_HEADING_WORDS = 6
_HEADING_STRIP = re.compile(r"^[\s*#>|\-=_.:]+|[\s*#>|\-=_:]+$")


@dataclass
class Section:
    name: str  # canonical name, e.g. "Projects"
    heading: str  # the literal line found in the document ("KEY PROJECTS")
    text: str  # body text, heading excluded
    char_start: int  # offset into the cleaned document text
    char_end: int


def _normalize_heading(line: str) -> str:
    line = _HEADING_STRIP.sub("", line)
    return re.sub(r"\s+", " ", line).strip().lower()


def _match_section(line: str, vocabulary: Dict[str, List[str]]) -> Optional[str]:
    """Return the canonical section name if `line` looks like its heading."""
    candidate = _normalize_heading(line)
    if not candidate or len(candidate) > _MAX_HEADING_LEN:
        return None
    if len(candidate.split()) > _MAX_HEADING_WORDS:
        return None
    # A real heading rarely ends in a full stop or comma.
    if candidate.endswith((".", ",", ";")):
        return None

    # Exact alias match wins.
    for name, aliases in vocabulary.items():
        if candidate in aliases:
            return name

    # Then a contained-alias match ("TECHNICAL SKILLS & TOOLS" -> Skills),
    # requiring the original line to look like a heading (caps or bold-ish),
    # so we don't misread a sentence that merely mentions the word.
    looks_like_heading = line.strip() == line.strip().upper() or len(candidate.split()) <= 3
    if looks_like_heading:
        for name, aliases in vocabulary.items():
            for alias in aliases:
                if len(alias) >= 5 and alias in candidate:
                    return name
    return None


def detect_sections(text: str, doc_type: str) -> List[Section]:
    """Split cleaned document text into labelled sections.

    `doc_type` is "resume" or "jd".
    """
    vocabulary = RESUME_SECTIONS if doc_type == "resume" else JD_SECTIONS
    fallback = DEFAULT_SECTION.get(doc_type, "Other")

    # Record (offset, line) so section boundaries map back to real offsets.
    lines: List[Tuple[int, str]] = []
    offset = 0
    for line in text.split("\n"):
        lines.append((offset, line))
        offset += len(line) + 1

    # Find every heading line.
    markers: List[Tuple[int, str, str]] = []  # (line_index, canonical, raw heading)
    for index, (_, line) in enumerate(lines):
        if not line.strip():
            continue
        name = _match_section(line, vocabulary)
        if name:
            markers.append((index, name, line.strip()))

    sections: List[Section] = []

    # Anything before the first heading is the preamble (name/contact block on a
    # resume, intro paragraph on a JD).
    first_marker = markers[0][0] if markers else len(lines)
    preamble = "\n".join(line for _, line in lines[:first_marker]).strip()
    if preamble:
        preamble_name = "Contact" if doc_type == "resume" else "About"
        sections.append(
            Section(
                name=preamble_name,
                heading="",
                text=preamble,
                char_start=0,
                char_end=lines[first_marker][0] if first_marker < len(lines) else len(text),
            )
        )

    for position, (line_index, name, heading) in enumerate(markers):
        body_start_line = line_index + 1
        next_line = markers[position + 1][0] if position + 1 < len(markers) else len(lines)

        body = "\n".join(line for _, line in lines[body_start_line:next_line]).strip()
        if not body:
            continue

        char_start = lines[body_start_line][0] if body_start_line < len(lines) else len(text)
        char_end = lines[next_line][0] if next_line < len(lines) else len(text)

        sections.append(
            Section(
                name=name,
                heading=heading,
                text=body,
                char_start=char_start,
                char_end=char_end,
            )
        )

    # A document with no recognisable headings still needs one section.
    if not sections:
        sections.append(
            Section(name=fallback, heading="", text=text, char_start=0, char_end=len(text))
        )

    return sections


def section_names(sections: List[Section]) -> List[str]:
    seen: List[str] = []
    for section in sections:
        if section.name not in seen:
            seen.append(section.name)
    return seen
