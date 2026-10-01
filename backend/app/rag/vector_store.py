"""STAGE 6 -- Vector storage and search.

The vector store is the "database" half of RAG. It holds one row per chunk:

    id -> (vector, chunk text, metadata)

and answers one question fast: *given this query vector, which chunks are
closest?* Closeness is cosine similarity -- the angle between two vectors.

Two backends, one interface:

* `ChromaVectorStore` -- ChromaDB, a real embedded vector database with
  on-disk persistence and metadata filtering. Used when installed.
* `NumpyVectorStore` -- a transparent ~100-line implementation: store the
  vectors in a matrix, compute `matrix @ query` for the scores, sort. For the
  handful of chunks a resume + JD produce this is instant, and it makes the
  maths visible instead of hiding it behind a library.

Everything is scoped by `session_id` so two users' documents can never mix.
"""

import json
import shutil
import threading
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from app.core.config import Settings
from app.core.errors import VectorStoreError
from app.core.logging import get_logger
from app.rag.chunking import Chunk

logger = get_logger(__name__)


@dataclass
class SearchHit:
    chunk_id: str
    text: str
    score: float  # cosine similarity in [0, 1]
    metadata: Dict[str, Any]

    @property
    def doc_type(self) -> str:
        return str(self.metadata.get("doc_type", "resume"))

    @property
    def section(self) -> str:
        return str(self.metadata.get("section", "Other"))

    @property
    def page(self) -> int:
        return int(self.metadata.get("page", 1))

    @property
    def citation(self) -> str:
        label = "Resume" if self.doc_type == "resume" else "Job Description"
        return f"{label} -> {self.section} -> Page {self.page}"


class BaseVectorStore:
    name = "base"
    display_name = "Base"

    def add(self, session_id: str, chunks: Sequence[Chunk], vectors: np.ndarray) -> None:
        raise NotImplementedError

    def search(
        self,
        session_id: str,
        query_vector: np.ndarray,
        top_k: int = 8,
        doc_type: Optional[str] = None,
        sections: Optional[Sequence[str]] = None,
    ) -> List[SearchHit]:
        raise NotImplementedError

    def get_vectors(self, session_id: str, chunk_ids: Sequence[str]) -> Dict[str, np.ndarray]:
        raise NotImplementedError

    def delete_session(self, session_id: str) -> None:
        raise NotImplementedError

    def delete_document(self, session_id: str, doc_id: str) -> None:
        raise NotImplementedError

    def count(self, session_id: str) -> int:
        raise NotImplementedError

    def info(self) -> dict:
        return {"backend": self.name, "name": self.display_name}


# --------------------------------------------------------------------------
# Backend 1: NumPy (always available)
# --------------------------------------------------------------------------
class NumpyVectorStore(BaseVectorStore):
    """Brute-force cosine search over a per-session matrix, persisted to disk.

    Brute force sounds slow, but a resume + JD is ~40 chunks. Scanning 40
    vectors of 384 floats is microseconds -- an approximate index (HNSW/IVF)
    only pays off in the millions.
    """

    name = "numpy"
    display_name = "NumPy cosine store"

    def __init__(self, directory) -> None:
        self._dir = directory
        self._dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._cache: Dict[str, Dict[str, Any]] = {}

    # -- persistence ------------------------------------------------------
    def _path(self, session_id: str):
        return self._dir / f"{session_id}.npz"

    def _load(self, session_id: str) -> Dict[str, Any]:
        if session_id in self._cache:
            return self._cache[session_id]

        path = self._path(session_id)
        if path.exists():
            try:
                with np.load(path, allow_pickle=False) as data:
                    payload = {
                        "ids": list(data["ids"]),
                        "vectors": data["vectors"].astype(np.float32),
                        "records": json.loads(str(data["records"])),
                    }
            except Exception as exc:
                logger.warning("Could not read vector file for %s (%s); rebuilding.", session_id, exc)
                payload = {"ids": [], "vectors": np.zeros((0, 0), dtype=np.float32), "records": {}}
        else:
            payload = {"ids": [], "vectors": np.zeros((0, 0), dtype=np.float32), "records": {}}

        self._cache[session_id] = payload
        return payload

    def _save(self, session_id: str, payload: Dict[str, Any]) -> None:
        try:
            np.savez_compressed(
                self._path(session_id),
                ids=np.array(payload["ids"], dtype=object).astype("U"),
                vectors=payload["vectors"],
                records=json.dumps(payload["records"]),
            )
        except Exception as exc:
            raise VectorStoreError(f"Could not persist vectors: {exc}") from exc

    # -- interface --------------------------------------------------------
    def add(self, session_id: str, chunks: Sequence[Chunk], vectors: np.ndarray) -> None:
        if len(chunks) == 0:
            return
        with self._lock:
            payload = self._load(session_id)

            # Re-uploading the same document replaces its old chunks.
            incoming_ids = {chunk.chunk_id for chunk in chunks}
            keep = [i for i, cid in enumerate(payload["ids"]) if cid not in incoming_ids]
            existing_vectors = (
                payload["vectors"][keep] if payload["vectors"].size and keep else None
            )
            ids = [payload["ids"][i] for i in keep]
            records = {cid: payload["records"][cid] for cid in ids if cid in payload["records"]}

            new_vectors = np.asarray(vectors, dtype=np.float32)
            # Normalise so a dot product equals cosine similarity.
            norms = np.linalg.norm(new_vectors, axis=1, keepdims=True)
            new_vectors = new_vectors / np.clip(norms, 1e-9, None)

            if existing_vectors is not None and existing_vectors.size:
                matrix = np.vstack([existing_vectors, new_vectors])
            else:
                matrix = new_vectors

            for chunk in chunks:
                ids.append(chunk.chunk_id)
                records[chunk.chunk_id] = {
                    "text": chunk.text,
                    "metadata": chunk.to_metadata(),
                }

            payload = {"ids": ids, "vectors": matrix, "records": records}
            self._cache[session_id] = payload
            self._save(session_id, payload)

    def search(
        self,
        session_id: str,
        query_vector: np.ndarray,
        top_k: int = 8,
        doc_type: Optional[str] = None,
        sections: Optional[Sequence[str]] = None,
    ) -> List[SearchHit]:
        payload = self._load(session_id)
        if not payload["ids"] or payload["vectors"].size == 0:
            return []

        query = np.asarray(query_vector, dtype=np.float32)
        norm = np.linalg.norm(query)
        if norm == 0:
            return []
        query = query / norm

        # THE core RAG operation: one matrix multiply gives the similarity of
        # the question against every chunk at once.
        scores = payload["vectors"] @ query

        wanted_sections = {s.lower() for s in sections} if sections else None
        candidates: List[SearchHit] = []
        for index, chunk_id in enumerate(payload["ids"]):
            record = payload["records"].get(chunk_id)
            if not record:
                continue
            metadata = record["metadata"]
            if doc_type and metadata.get("doc_type") != doc_type:
                continue
            if wanted_sections and str(metadata.get("section", "")).lower() not in wanted_sections:
                continue
            candidates.append(
                SearchHit(
                    chunk_id=chunk_id,
                    text=record["text"],
                    score=float(max(0.0, min(1.0, scores[index]))),
                    metadata=metadata,
                )
            )

        candidates.sort(key=lambda hit: hit.score, reverse=True)
        return candidates[:top_k]

    def get_vectors(self, session_id: str, chunk_ids: Sequence[str]) -> Dict[str, np.ndarray]:
        payload = self._load(session_id)
        position = {cid: i for i, cid in enumerate(payload["ids"])}
        result: Dict[str, np.ndarray] = {}
        for chunk_id in chunk_ids:
            index = position.get(chunk_id)
            if index is not None:
                result[chunk_id] = payload["vectors"][index]
        return result

    def delete_session(self, session_id: str) -> None:
        with self._lock:
            self._cache.pop(session_id, None)
            path = self._path(session_id)
            if path.exists():
                path.unlink()

    def delete_document(self, session_id: str, doc_id: str) -> None:
        with self._lock:
            payload = self._load(session_id)
            keep = [
                i
                for i, cid in enumerate(payload["ids"])
                if payload["records"].get(cid, {}).get("metadata", {}).get("doc_id") != doc_id
            ]
            if len(keep) == len(payload["ids"]):
                return
            ids = [payload["ids"][i] for i in keep]
            payload = {
                "ids": ids,
                "vectors": payload["vectors"][keep] if keep else np.zeros((0, 0), dtype=np.float32),
                "records": {cid: payload["records"][cid] for cid in ids},
            }
            self._cache[session_id] = payload
            self._save(session_id, payload)

    def count(self, session_id: str) -> int:
        return len(self._load(session_id)["ids"])


# --------------------------------------------------------------------------
# Backend 2: ChromaDB
# --------------------------------------------------------------------------
class ChromaVectorStore(BaseVectorStore):
    name = "chroma"
    display_name = "ChromaDB"

    COLLECTION = "rag_chunks"

    def __init__(self, directory) -> None:
        import chromadb
        from chromadb.config import Settings as ChromaSettings

        self._client = chromadb.PersistentClient(
            path=str(directory),
            settings=ChromaSettings(anonymized_telemetry=False, allow_reset=True),
        )
        self._collection = self._client.get_or_create_collection(
            name=self.COLLECTION,
            # Chroma would otherwise embed for us; we pass our own vectors so
            # both backends use the exact same embedding model.
            metadata={"hnsw:space": "cosine"},
            embedding_function=None,
        )
        logger.info("ChromaDB ready at %s", directory)

    def _where(
        self,
        session_id: str,
        doc_type: Optional[str],
        sections: Optional[Sequence[str]],
    ) -> Dict[str, Any]:
        clauses: List[Dict[str, Any]] = [{"session_id": {"$eq": session_id}}]
        if doc_type:
            clauses.append({"doc_type": {"$eq": doc_type}})
        if sections:
            clauses.append({"section": {"$in": list(sections)}})
        return clauses[0] if len(clauses) == 1 else {"$and": clauses}

    def add(self, session_id: str, chunks: Sequence[Chunk], vectors: np.ndarray) -> None:
        if len(chunks) == 0:
            return
        try:
            ids = [f"{session_id}:{chunk.chunk_id}" for chunk in chunks]
            # Upsert semantics: delete first so re-uploads don't duplicate.
            self._collection.delete(ids=ids)
            self._collection.add(
                ids=ids,
                embeddings=[vector.tolist() for vector in np.asarray(vectors, dtype=np.float32)],
                documents=[chunk.text for chunk in chunks],
                metadatas=[dict(chunk.to_metadata(), session_id=session_id) for chunk in chunks],
            )
        except Exception as exc:
            logger.exception("Chroma add failed")
            raise VectorStoreError(f"Could not store vectors: {exc}") from exc

    def search(
        self,
        session_id: str,
        query_vector: np.ndarray,
        top_k: int = 8,
        doc_type: Optional[str] = None,
        sections: Optional[Sequence[str]] = None,
    ) -> List[SearchHit]:
        try:
            result = self._collection.query(
                query_embeddings=[np.asarray(query_vector, dtype=np.float32).tolist()],
                n_results=max(1, top_k),
                where=self._where(session_id, doc_type, sections),
                include=["documents", "metadatas", "distances"],
            )
        except Exception as exc:
            logger.exception("Chroma query failed")
            raise VectorStoreError(f"Vector search failed: {exc}") from exc

        hits: List[SearchHit] = []
        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]

        for text, metadata, distance in zip(documents, metadatas, distances):
            metadata = dict(metadata or {})
            hits.append(
                SearchHit(
                    chunk_id=str(metadata.get("chunk_id", "")),
                    text=text or "",
                    # Chroma returns cosine *distance*; similarity = 1 - distance.
                    score=float(max(0.0, min(1.0, 1.0 - float(distance)))),
                    metadata=metadata,
                )
            )
        return hits

    def get_vectors(self, session_id: str, chunk_ids: Sequence[str]) -> Dict[str, np.ndarray]:
        if not chunk_ids:
            return {}
        try:
            result = self._collection.get(
                ids=[f"{session_id}:{cid}" for cid in chunk_ids],
                include=["embeddings", "metadatas"],
            )
        except Exception as exc:
            raise VectorStoreError(f"Could not read vectors: {exc}") from exc

        vectors: Dict[str, np.ndarray] = {}
        embeddings = result.get("embeddings") or []
        metadatas = result.get("metadatas") or []
        for embedding, metadata in zip(embeddings, metadatas):
            chunk_id = str((metadata or {}).get("chunk_id", ""))
            if chunk_id:
                vectors[chunk_id] = np.asarray(embedding, dtype=np.float32)
        return vectors

    def delete_session(self, session_id: str) -> None:
        try:
            self._collection.delete(where={"session_id": {"$eq": session_id}})
        except Exception as exc:
            logger.warning("Chroma delete failed for %s: %s", session_id, exc)

    def delete_document(self, session_id: str, doc_id: str) -> None:
        try:
            self._collection.delete(
                where={"$and": [{"session_id": {"$eq": session_id}}, {"doc_id": {"$eq": doc_id}}]}
            )
        except Exception as exc:
            logger.warning("Chroma document delete failed: %s", exc)

    def count(self, session_id: str) -> int:
        try:
            result = self._collection.get(
                where={"session_id": {"$eq": session_id}}, include=[]
            )
            return len(result.get("ids") or [])
        except Exception:
            return 0


# --------------------------------------------------------------------------
# Factory
# --------------------------------------------------------------------------
_store: Optional[BaseVectorStore] = None
_store_lock = threading.Lock()


def get_vector_store(settings: Settings) -> BaseVectorStore:
    global _store
    if _store is not None:
        return _store

    with _store_lock:
        if _store is not None:
            return _store

        backend = settings.vector_store.lower()

        if backend in ("auto", "chroma"):
            try:
                _store = ChromaVectorStore(settings.chroma_dir)
                return _store
            except ImportError:
                if backend == "chroma":
                    raise VectorStoreError(
                        "VECTOR_STORE=chroma but chromadb isn't installed.",
                        hint="Run `pip install chromadb`, or set VECTOR_STORE=auto.",
                    )
                logger.info("chromadb not installed -- using the built-in NumPy vector store.")
            except Exception as exc:
                if backend == "chroma":
                    raise VectorStoreError(f"Could not open ChromaDB: {exc}")
                logger.warning("ChromaDB unavailable (%s); using the NumPy store.", exc)

        _store = NumpyVectorStore(settings.vectors_dir)
        return _store


def reset_vector_store() -> None:
    global _store
    _store = None


def purge_all(settings: Settings) -> None:
    """Delete every stored vector. Used by the maintenance endpoint."""
    reset_vector_store()
    for directory in (settings.chroma_dir, settings.vectors_dir):
        if directory.exists():
            shutil.rmtree(directory, ignore_errors=True)
        directory.mkdir(parents=True, exist_ok=True)
