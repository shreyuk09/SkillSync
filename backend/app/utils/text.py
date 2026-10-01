"""Small text helpers shared by the RAG modules and the analysis services."""

import re
import unicodedata
from typing import Iterable, List, Set

_WORD = re.compile(r"[A-Za-z0-9+#.\-]+")

# Words that carry no signal when we compare a resume to a job description.
STOPWORDS: Set[str] = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has", "have",
    "in", "is", "it", "its", "of", "on", "or", "that", "the", "to", "was", "were",
    "will", "with", "you", "your", "our", "we", "they", "this", "these", "those",
    "using", "used", "use", "able", "must", "should", "would", "can", "may",
    "work", "working", "experience", "years", "year", "strong", "good", "excellent",
    "knowledge", "understanding", "ability", "including", "etc", "plus", "role",
    "team", "teams", "job", "candidate", "candidates", "required", "requirements",
    "preferred", "responsibilities", "qualifications", "about", "who", "what",
}


def normalize_whitespace(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def normalize_token(token: str) -> str:
    """Lower-case, strip accents and trailing punctuation. Keeps `c++`, `.net`."""
    token = unicodedata.normalize("NFKD", token)
    token = "".join(ch for ch in token if not unicodedata.combining(ch))
    return token.lower().strip(".,;:()[]{}\"'`")


def tokenize(text: str) -> List[str]:
    return [normalize_token(match.group()) for match in _WORD.finditer(text)]


def content_tokens(text: str) -> List[str]:
    """Tokens worth comparing: no stopwords, no single characters."""
    return [t for t in tokenize(text) if t and t not in STOPWORDS and len(t) > 1]


def truncate(text: str, limit: int, suffix: str = "...") -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - len(suffix))].rstrip() + suffix


def unique_preserving_order(items: Iterable[str]) -> List[str]:
    seen: Set[str] = set()
    result: List[str] = []
    for item in items:
        key = item.lower().strip()
        if key and key not in seen:
            seen.add(key)
            result.append(item.strip())
    return result
