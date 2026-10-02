"""STAGE 5 -- Embeddings.

An embedding turns a piece of text into a list of numbers (a vector) that
captures its *meaning*. Two texts that mean similar things end up close
together in that space, even when they share no words: "built a REST endpoint
in Flask" lands near "designed backend APIs". That is exactly why this project
is retrieval-augmented rather than keyword search.

Two providers are shipped behind one interface:

* `SentenceTransformerEmbedder` -- a real neural embedding model
  (all-MiniLM-L6-v2, 384 dimensions). Runs locally, free, no API key.
  This is the default when `sentence-transformers` is installed.

* `HashingEmbedder` -- a dependency-free fallback that hashes word and
  character n-grams into a fixed vector. It captures lexical overlap and
  morphology but NOT true synonymy. The API reports which one is active so
  the UI can be honest about it.

Embeddings are computed locally -- the hosted LLM is used for the
*generation* step only. That separation is normal in RAG: a small, cheap model
does retrieval; a large model does reasoning.
"""

import hashlib
import math
import re
import threading
from typing import List, Optional, Sequence

import numpy as np

from app.core.config import Settings
from app.core.errors import EmbeddingError
from app.core.logging import get_logger

logger = get_logger(__name__)

_WORD_RE = re.compile(r"[a-z0-9+#.]+")


class BaseEmbedder:
    """Interface every embedding provider implements."""

    name: str = "base"
    display_name: str = "Base"
    dimension: int = 0
    is_semantic: bool = False

    def embed_documents(self, texts: Sequence[str]) -> np.ndarray:
        raise NotImplementedError

    def embed_query(self, text: str) -> np.ndarray:
        return self.embed_documents([text])[0]

    def info(self) -> dict:
        return {
            "provider": self.name,
            "model": self.display_name,
            "dimension": self.dimension,
            "semantic": self.is_semantic,
        }


# --------------------------------------------------------------------------
# Provider 1: real sentence embeddings (preferred)
# --------------------------------------------------------------------------
class SentenceTransformerEmbedder(BaseEmbedder):
    name = "local"
    is_semantic = True

    def __init__(self, model_name: str) -> None:
        from sentence_transformers import SentenceTransformer  # imported lazily

        logger.info("Loading embedding model '%s' (first run downloads ~90 MB)...", model_name)
        self._model = SentenceTransformer(model_name)
        self.display_name = model_name
        self.dimension = int(self._model.get_sentence_embedding_dimension())
        logger.info("Embedding model ready (%d dimensions).", self.dimension)

    def embed_documents(self, texts: Sequence[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dimension), dtype=np.float32)
        try:
            vectors = self._model.encode(
                list(texts),
                batch_size=32,
                convert_to_numpy=True,
                normalize_embeddings=True,  # so a dot product IS cosine similarity
                show_progress_bar=False,
            )
            return np.asarray(vectors, dtype=np.float32)
        except Exception as exc:
            logger.exception("Embedding failed")
            raise EmbeddingError(
                "The embedding model failed while indexing your document."
            ) from exc


# --------------------------------------------------------------------------
# Provider 2: dependency-free fallback
# --------------------------------------------------------------------------
class HashingEmbedder(BaseEmbedder):
    """Hashes words + character trigrams into a fixed-size vector.

    Not a neural model: it can't know that "ML" and "machine learning" are
    related unless the characters overlap. It is here so the project runs on
    any machine with zero downloads, and so a failed model load degrades
    instead of crashing.
    """

    name = "hash"
    display_name = "Built-in hashing embedder (fallback)"
    is_semantic = False

    def __init__(self, dimension: int = 512) -> None:
        self.dimension = dimension

    @staticmethod
    def _bucket(token: str, dimension: int) -> int:
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        return int.from_bytes(digest, "big") % dimension

    def _features(self, text: str) -> List[str]:
        words = _WORD_RE.findall(text.lower())
        features: List[str] = list(words)
        # Word bigrams capture short phrases ("machine learning").
        features.extend(f"{a}_{b}" for a, b in zip(words, words[1:]))
        # Character trigrams give partial credit for morphology
        # ("containerised" ~ "container").
        for word in words:
            if len(word) > 4:
                padded = f"#{word}#"
                features.extend(padded[i : i + 3] for i in range(len(padded) - 2))
        return features

    def embed_documents(self, texts: Sequence[str]) -> np.ndarray:
        matrix = np.zeros((len(texts), self.dimension), dtype=np.float32)
        for row, text in enumerate(texts):
            counts: dict = {}
            for feature in self._features(text):
                bucket = self._bucket(feature, self.dimension)
                counts[bucket] = counts.get(bucket, 0) + 1
            for bucket, count in counts.items():
                # Sublinear term frequency, same idea as TF-IDF: the 10th
                # mention of "Python" matters much less than the 1st.
                matrix[row, bucket] = 1.0 + math.log(count)
            norm = np.linalg.norm(matrix[row])
            if norm > 0:
                matrix[row] /= norm
        return matrix


# --------------------------------------------------------------------------
# Factory
# --------------------------------------------------------------------------
_embedder: Optional[BaseEmbedder] = None
_lock = threading.Lock()


def get_embedder(settings: Settings) -> BaseEmbedder:
    """Return the process-wide embedder, loading it on first use."""
    global _embedder
    if _embedder is not None:
        return _embedder

    with _lock:
        if _embedder is not None:
            return _embedder

        provider = settings.embedding_provider.lower()

        if provider in ("auto", "local"):
            try:
                _embedder = SentenceTransformerEmbedder(settings.embedding_model)
                return _embedder
            except ImportError:
                if provider == "local":
                    raise EmbeddingError(
                        "EMBEDDING_PROVIDER=local but sentence-transformers isn't installed.",
                        hint="Run `pip install sentence-transformers`, or set EMBEDDING_PROVIDER=auto.",
                    )
                logger.warning(
                    "sentence-transformers not installed -- falling back to the built-in "
                    "hashing embedder. Install it for true semantic search."
                )
            except Exception as exc:
                if provider == "local":
                    raise EmbeddingError(f"Could not load '{settings.embedding_model}': {exc}")
                logger.warning("Could not load the embedding model (%s); using the fallback.", exc)

        _embedder = HashingEmbedder()
        return _embedder


def reset_embedder() -> None:
    """Test hook -- drop the cached embedder."""
    global _embedder
    _embedder = None


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two vectors, clamped to [0, 1]."""
    denominator = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denominator == 0.0:
        return 0.0
    return max(0.0, min(1.0, float(np.dot(a, b)) / denominator))
