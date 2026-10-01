"""STAGE 7 -- Retrieval.

Given a question, find the chunks most likely to contain the answer.

Four refinements over a plain top-k similarity search:

1. **Hybrid search (dense + BM25, fused with RRF).** A small bi-encoder is
   excellent at synonymy but weak on short queries against long passages. Asked
   "which of my projects is most relevant?", pure cosine ranked this project's
   sample resume like this:

       0.336  Skills          0.327  Achievements   ...   0.215  Projects

   The Projects section -- the literal answer -- came fourth. Adding a BM25
   lexical ranking and fusing the two by Reciprocal Rank Fusion fixes that
   without giving up synonymy: dense still finds "containerised deployments"
   for a Docker query, while BM25 makes sure a passage that says "Projects"
   wins a question about projects. This is hybrid retrieval, the standard
   production answer, not a fallback to keyword search.

2. **Section-intent boost.** "What are the education requirements?" should
   prefer chunks from the Education / Requirements sections. Because every
   chunk carries its section as metadata, that's a cheap, honest signal.

3. **MMR (Maximal Marginal Relevance).** Plain top-k often returns five
   near-duplicate chunks. MMR trades a little relevance for diversity, so the
   LLM sees *different* evidence instead of the same sentence five times.

4. **A relevance floor.** Chunks below `MIN_SCORE` are dropped. If nothing
   clears the floor the caller gets an empty list -- which is what lets the
   assistant say "I couldn't find that in your documents" instead of
   hallucinating an answer from weak context.

`retrieve_pair` sits on top of all of this and guarantees a quota from the
resume *and* from the job description, because almost every question here needs
evidence from both sides of the comparison.
"""

import math
from collections import Counter
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from app.core.config import Settings
from app.rag.embeddings import get_embedder
from app.rag.vector_store import SearchHit, get_vector_store
from app.utils.text import content_tokens

# Below this cosine similarity a chunk is treated as unrelated to the query.
MIN_SCORE = 0.06
MMR_LAMBDA = 0.7  # 1.0 = pure relevance, 0.0 = pure diversity

# Reciprocal Rank Fusion. Score for a document at rank r (0-indexed) is
# weight / (RRF_K + r + 1). The constant damps the difference between the top
# ranks so one ranking can't completely dominate the other.
RRF_K = 60
DENSE_WEIGHT = 1.0
LEXICAL_WEIGHT = 0.65
SECTION_BOOST = 0.5 / (RRF_K + 1)

# Words in a question that signal the user is asking about a specific section.
SECTION_INTENT: Dict[str, Sequence[str]] = {
    "Projects": ("project", "projects", "built", "build", "portfolio", "app", "application"),
    "Experience": ("experience", "work", "worked", "job", "jobs", "role", "roles", "employment"),
    "Internships": ("internship", "internships", "intern", "training"),
    "Skills": ("skill", "skills", "technology", "technologies", "stack", "tools", "languages"),
    "Education": ("education", "degree", "college", "university", "cgpa", "gpa", "study",
                  "studied", "academic", "graduation"),
    "Certifications": ("certification", "certifications", "certificate", "certified", "course", "courses"),
    "Achievements": ("achievement", "achievements", "award", "awards", "hackathon", "won", "winner"),
    "Publications": ("publication", "publications", "paper", "papers", "research"),
    "Summary": ("summary", "objective", "about"),
    "Responsibilities": ("responsibility", "responsibilities", "duties", "day-to-day", "involve", "involves"),
    "Requirements": ("requirement", "requirements", "require", "requires", "required",
                     "qualification", "qualifications", "must", "need", "needs"),
    "Preferred": ("preferred", "nice", "bonus", "optional", "desirable"),
    "About": ("company", "about", "team", "organisation", "organization"),
}


def _bm25_scores(query: str, documents: Sequence[str]) -> List[float]:
    """Classic BM25 over a small candidate set.

    The candidate set doubles as the corpus for the IDF term. With a resume and
    a job description that's a few dozen passages, which is plenty for term
    rarity to be meaningful and cheap enough to compute per query.
    """
    k1, b = 1.5, 0.75
    tokenized = [content_tokens(document) for document in documents]
    if not tokenized:
        return []

    lengths = [len(tokens) for tokens in tokenized]
    average_length = (sum(lengths) / len(lengths)) or 1.0
    total = len(tokenized)

    document_frequency: Counter = Counter()
    for tokens in tokenized:
        document_frequency.update(set(tokens))

    query_terms = content_tokens(query)
    scores: List[float] = []

    for tokens, length in zip(tokenized, lengths):
        frequencies = Counter(tokens)
        score = 0.0
        for term in query_terms:
            frequency = frequencies.get(term, 0)
            if not frequency:
                continue
            appearances = document_frequency[term]
            idf = math.log(1 + (total - appearances + 0.5) / (appearances + 0.5))
            numerator = frequency * (k1 + 1)
            denominator = frequency + k1 * (1 - b + b * length / average_length)
            score += idf * numerator / denominator
        scores.append(score)

    return scores


def _intended_sections(query: str) -> set:
    """Which sections does this question seem to be about? Possibly none."""
    tokens = set(content_tokens(query))
    return {
        section
        for section, hints in SECTION_INTENT.items()
        if tokens.intersection(hints)
    }


@dataclass
class RetrievedChunk:
    """A retrieved chunk plus the label the UI shows as its source."""

    chunk_id: str
    text: str
    score: float  # raw cosine similarity of the embeddings
    doc_type: str
    doc_name: str
    section: str
    page: int
    ref: str = ""  # "S1", "S2", ... assigned when building a prompt
    # Final relevance after hybrid fusion, 0..1. This is what the ordering
    # reflects; `score` is kept separately so the cosine is still visible.
    rank_score: float = 0.0

    @property
    def citation(self) -> str:
        label = "Resume" if self.doc_type == "resume" else "Job Description"
        return f"{label} -> {self.section} -> Page {self.page}"

    def to_source(self) -> dict:
        return {
            "ref": self.ref,
            "chunk_id": self.chunk_id,
            "doc_type": self.doc_type,
            "doc_name": self.doc_name,
            "section": self.section,
            "page": self.page,
            "score": round(self.score, 4),
            "rank_score": round(self.rank_score, 4),
            "citation": self.citation,
            "text": self.text,
        }


def _to_retrieved(hit: SearchHit, rank_score: Optional[float] = None) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=hit.chunk_id,
        text=hit.text,
        score=hit.score,
        doc_type=hit.doc_type,
        doc_name=str(hit.metadata.get("doc_name", "")),
        section=hit.section,
        page=hit.page,
        rank_score=hit.score if rank_score is None else rank_score,
    )


class Retriever:
    """Wraps the embedder + vector store into the retrieval half of RAG."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._embedder = get_embedder(settings)
        self._store = get_vector_store(settings)

    # -- basics ------------------------------------------------------------
    def embed(self, text: str) -> np.ndarray:
        return self._embedder.embed_query(text)

    def embed_many(self, texts: Sequence[str]) -> np.ndarray:
        return self._embedder.embed_documents(list(texts))

    @property
    def embedder_info(self) -> dict:
        return self._embedder.info()

    @property
    def store_info(self) -> dict:
        return self._store.info()

    # -- retrieval ---------------------------------------------------------
    def retrieve(
        self,
        session_id: str,
        query: str,
        *,
        top_k: Optional[int] = None,
        doc_type: Optional[str] = None,
        sections: Optional[Sequence[str]] = None,
        min_score: float = MIN_SCORE,
        use_mmr: bool = True,
        hybrid: bool = True,
    ) -> List[RetrievedChunk]:
        """Retrieve the passages most likely to answer `query`.

        `hybrid=False` gives pure dense similarity. That is what the skill
        classifier wants: it runs its own lexical test separately, so mixing
        BM25 in here would count the same evidence twice.
        """
        top_k = top_k or self._settings.retrieval_top_k
        query_vector = self._embedder.embed_query(query)

        # Over-fetch: hybrid fusion and MMR both need candidates to work with.
        fetch_k = top_k * 4 if (use_mmr or hybrid) else top_k
        hits = self._store.search(
            session_id, query_vector, top_k=fetch_k, doc_type=doc_type, sections=sections
        )
        hits = [hit for hit in hits if hit.score >= min_score]
        if not hits:
            return []

        relevance: Optional[Dict[str, float]] = None
        if hybrid and len(hits) > 1:
            hits, relevance = self._fuse(query, hits)

        if not use_mmr or len(hits) <= top_k:
            return [
                _to_retrieved(hit, (relevance or {}).get(hit.chunk_id))
                for hit in hits[:top_k]
            ]

        return self._mmr(session_id, query_vector, hits, top_k, relevance)

    def _fuse(self, query: str, hits: List[SearchHit]):
        """Fuse the dense ranking with a BM25 ranking using RRF.

        RRF combines *ranks*, not scores, so it doesn't matter that cosine
        similarity and BM25 live on completely different scales -- a persistent
        problem with naive score-weighted blending.
        """
        # `hits` already arrives sorted by cosine similarity.
        dense_rank = {hit.chunk_id: rank for rank, hit in enumerate(hits)}

        scores = _bm25_scores(query, [hit.text for hit in hits])
        lexical_score = {hit.chunk_id: scores[i] for i, hit in enumerate(hits)}
        lexical_order = sorted(range(len(hits)), key=lambda i: scores[i], reverse=True)
        lexical_rank = {
            hits[index].chunk_id: rank for rank, index in enumerate(lexical_order)
        }

        wanted_sections = _intended_sections(query)

        def fused(hit: SearchHit) -> float:
            score = DENSE_WEIGHT / (RRF_K + dense_rank[hit.chunk_id] + 1)
            # A chunk containing no query term at all gets no lexical credit,
            # rather than credit for merely being least-bad in that ranking.
            if lexical_score[hit.chunk_id] > 0:
                score += LEXICAL_WEIGHT / (RRF_K + lexical_rank[hit.chunk_id] + 1)
            if hit.section in wanted_sections:
                score += SECTION_BOOST
            return score

        fused_scores = {hit.chunk_id: fused(hit) for hit in hits}
        ordered = sorted(hits, key=lambda hit: fused_scores[hit.chunk_id], reverse=True)

        # Rescale to 0..1 so MMR can weigh fused relevance against redundancy,
        # which lives on the cosine scale.
        values = list(fused_scores.values())
        low, high = min(values), max(values)
        span = (high - low) or 1.0
        relevance = {
            chunk_id: (score - low) / span for chunk_id, score in fused_scores.items()
        }

        return ordered, relevance

    def _mmr(
        self,
        session_id: str,
        query_vector: np.ndarray,
        hits: List[SearchHit],
        top_k: int,
        relevance_by_id: Optional[Dict[str, float]] = None,
    ) -> List[RetrievedChunk]:
        """Greedily pick chunks that are relevant *and* unlike what's picked.

        `relevance_by_id` carries the hybrid-fused relevance. Without it MMR
        would fall back to raw cosine and silently undo the fusion.
        """
        vectors = self._store.get_vectors(session_id, [hit.chunk_id for hit in hits])
        if not vectors:
            return [
                _to_retrieved(hit, (relevance_by_id or {}).get(hit.chunk_id))
                for hit in hits[:top_k]
            ]

        def unit(vector: np.ndarray) -> np.ndarray:
            norm = np.linalg.norm(vector)
            return vector / norm if norm else vector

        query_unit = unit(np.asarray(query_vector, dtype=np.float32))
        pool: List[SearchHit] = [hit for hit in hits if hit.chunk_id in vectors]
        selected: List[SearchHit] = []
        selected_vectors: List[np.ndarray] = []

        while pool and len(selected) < top_k:
            best_hit = None
            best_value = -2.0
            for hit in pool:
                vector = unit(vectors[hit.chunk_id])
                relevance = (
                    relevance_by_id[hit.chunk_id]
                    if relevance_by_id is not None and hit.chunk_id in relevance_by_id
                    else float(np.dot(vector, query_unit))
                )
                redundancy = (
                    max(float(np.dot(vector, other)) for other in selected_vectors)
                    if selected_vectors
                    else 0.0
                )
                value = MMR_LAMBDA * relevance - (1.0 - MMR_LAMBDA) * redundancy
                if value > best_value:
                    best_value, best_hit = value, hit

            if best_hit is None:
                break
            selected.append(best_hit)
            selected_vectors.append(unit(vectors[best_hit.chunk_id]))
            pool.remove(best_hit)

        return [
            _to_retrieved(hit, (relevance_by_id or {}).get(hit.chunk_id))
            for hit in selected
        ]

    def retrieve_pair(
        self,
        session_id: str,
        query: str,
        *,
        resume_k: int = 5,
        jd_k: int = 4,
        min_score: float = MIN_SCORE,
    ) -> List[RetrievedChunk]:
        """Retrieve from the resume AND the job description, with quotas.

        Used by the chatbot and every cross-document analysis, so the model
        always sees both sides of the comparison.
        """
        resume_hits = self.retrieve(
            session_id, query, top_k=resume_k, doc_type="resume", min_score=min_score
        )
        jd_hits = self.retrieve(
            session_id, query, top_k=jd_k, doc_type="jd", min_score=min_score
        )
        # Sort by the fused rank score, not raw cosine -- sorting by cosine here
        # would throw away the hybrid ranking each side just computed. Each
        # side's scores are normalised within its own document, so this
        # interleaves "best from the resume" with "best from the JD", which is
        # exactly what a comparison question needs.
        combined = resume_hits + jd_hits
        combined.sort(key=lambda chunk: (chunk.rank_score, chunk.score), reverse=True)
        return combined

    def similarity_matrix(
        self, session_id: str, left_ids: Sequence[str], right_ids: Sequence[str]
    ) -> np.ndarray:
        """Cosine similarity between two sets of already-indexed chunks.

        This is how project relevance is scored: every project chunk against
        every JD requirement chunk, no LLM involved.
        """
        vectors = self._store.get_vectors(session_id, list(left_ids) + list(right_ids))
        if not vectors:
            return np.zeros((len(left_ids), len(right_ids)), dtype=np.float32)

        def matrix_for(ids: Sequence[str]) -> np.ndarray:
            rows = []
            dimension = len(next(iter(vectors.values())))
            for chunk_id in ids:
                vector = vectors.get(chunk_id)
                rows.append(np.zeros(dimension, dtype=np.float32) if vector is None else vector)
            stacked = np.vstack(rows) if rows else np.zeros((0, dimension), dtype=np.float32)
            norms = np.linalg.norm(stacked, axis=1, keepdims=True)
            return stacked / np.clip(norms, 1e-9, None)

        return matrix_for(left_ids) @ matrix_for(right_ids).T

    def max_similarity_to_text(
        self, session_id: str, text: str, *, doc_type: str, top_n: int = 3
    ) -> float:
        """How strongly is `text` supported by a document? Returns 0..1.

        Pure dense on purpose -- this measures *semantic* support.
        """
        hits = self.retrieve(
            session_id, text, top_k=top_n, doc_type=doc_type,
            min_score=0.0, use_mmr=False, hybrid=False,
        )
        return max((hit.score for hit in hits), default=0.0)

    def similarity_profile(
        self, session_id: str, query: str, *, doc_type: str
    ) -> Dict[str, Any]:
        """Best AND average similarity of a query across a whole document.

        An absolute cosine threshold is a poor test on its own, because every
        embedding model has its own baseline: some models score *everything*
        around 0.3, so "0.3 means related" is meaningless. Comparing the best
        chunk against the document's own average tells us whether one passage
        genuinely stands out -- which is the question we actually care about
        when deciding if a skill is evidenced.
        """
        hits = self.retrieve(
            session_id, query, top_k=200, doc_type=doc_type,
            min_score=0.0, use_mmr=False, hybrid=False,
        )
        if not hits:
            return {"best": 0.0, "mean": 0.0, "margin": 0.0, "best_hit": None}

        scores = [hit.score for hit in hits]
        best = max(scores)
        mean = sum(scores) / len(scores)
        return {
            "best": best,
            "mean": mean,
            "margin": best - mean,
            "best_hit": hits[0],
        }


def get_retriever(settings: Settings) -> Retriever:
    """A Retriever is cheap -- the embedder and store behind it are cached."""
    return Retriever(settings)
