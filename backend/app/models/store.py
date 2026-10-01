"""Application metadata database (SQLite).

Two databases sit side by side in this project, and it's worth being clear
about the split:

* **This one (SQLite)** stores *facts*: which session owns which documents,
  the extracted text, the chunk table, cached analysis results, chat history.
* **The vector store** stores *meaning*: one embedding per chunk, searched by
  similarity.

They're joined by `chunk_id`.

Privacy note: the uploaded file itself is never written to disk. Only the
extracted text is stored, scoped to a session, and `purge_expired()` deletes
sessions older than `SESSION_TTL_HOURS`.
"""

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from app.core.config import Settings
from app.core.errors import SessionNotFound
from app.core.logging import get_logger

logger = get_logger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id          TEXT PRIMARY KEY,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS documents (
    id            TEXT PRIMARY KEY,
    session_id    TEXT NOT NULL,
    doc_type      TEXT NOT NULL,          -- 'resume' | 'jd'
    name          TEXT NOT NULL,
    source_format TEXT NOT NULL,
    page_count    INTEGER NOT NULL,
    char_count    INTEGER NOT NULL,
    chunk_count   INTEGER NOT NULL,
    sections      TEXT NOT NULL,          -- JSON list of section names
    text          TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS chunks (
    chunk_id    TEXT PRIMARY KEY,
    session_id  TEXT NOT NULL,
    doc_id      TEXT NOT NULL,
    doc_type    TEXT NOT NULL,
    doc_name    TEXT NOT NULL,
    section     TEXT NOT NULL,
    page        INTEGER NOT NULL,
    chunk_index INTEGER NOT NULL,
    char_start  INTEGER NOT NULL,
    char_end    INTEGER NOT NULL,
    text        TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS analyses (
    session_id TEXT NOT NULL,
    kind       TEXT NOT NULL,             -- 'resume_profile' | 'match' | ...
    payload    TEXT NOT NULL,             -- JSON
    created_at TEXT NOT NULL,
    PRIMARY KEY (session_id, kind),
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role       TEXT NOT NULL,             -- 'user' | 'assistant'
    content    TEXT NOT NULL,
    sources    TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_documents_session ON documents(session_id, doc_type);
CREATE INDEX IF NOT EXISTS idx_chunks_session    ON chunks(session_id, doc_type);
CREATE INDEX IF NOT EXISTS idx_chat_session      ON chat_messages(session_id, id);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Store:
    """Thin, explicit SQLite wrapper. No ORM -- easy to read and to debug."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._lock = threading.RLock()
        self._connection = sqlite3.connect(
            settings.db_path, check_same_thread=False, timeout=15.0
        )
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA foreign_keys=ON")
        with self._lock:
            self._connection.executescript(SCHEMA)
            self._connection.commit()
            self._migrate()

    # -- migrations --------------------------------------------------------
    def _columns(self, table: str) -> List[str]:
        return [row["name"] for row in self._connection.execute(f"PRAGMA table_info({table})")]

    def _migrate(self) -> None:
        """Bring a database created by an older build up to date.

        A previous version stored several resumes and job descriptions per
        session, an "active pair" on the session row, and analyses keyed by
        that pair. A session now holds one of each, so those columns are
        dropped and any cached analysis is discarded rather than translated --
        a stale report from the multi-document build must not resurface next
        to whichever documents happen to remain.
        """
        with self._lock:
            tables = {
                row["name"]
                for row in self._connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            if "analysis_runs" in tables:
                self._connection.execute("DROP TABLE analysis_runs")
                logger.info("Dropped the analysis-run history table")

            if "pair_key" in self._columns("analyses"):
                self._connection.execute("DROP TABLE analyses")
                self._connection.executescript(SCHEMA)
                logger.info("Rebuilt the analysis cache without pair keys")

            session_columns = self._columns("sessions")
            if any(c in session_columns for c in ("active_resume_id", "active_jd_id")):
                # SQLite only learned DROP COLUMN in 3.35; rebuild for older ones.
                self._connection.execute(
                    "CREATE TABLE IF NOT EXISTS sessions_new ("
                    "id TEXT PRIMARY KEY, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"
                )
                self._connection.execute(
                    "INSERT OR REPLACE INTO sessions_new (id, created_at, updated_at) "
                    "SELECT id, created_at, updated_at FROM sessions"
                )
                self._connection.execute("DROP TABLE sessions")
                self._connection.execute("ALTER TABLE sessions_new RENAME TO sessions")
                logger.info("Dropped the active-pair columns from sessions")

            # Only one document of each type survives; drop the rest along with
            # their chunks so retrieval cannot reach them.
            for session_id, doc_type in self._connection.execute(
                "SELECT session_id, doc_type FROM documents "
                "GROUP BY session_id, doc_type HAVING COUNT(*) > 1"
            ).fetchall():
                keep = self._connection.execute(
                    "SELECT id FROM documents WHERE session_id = ? AND doc_type = ? "
                    "ORDER BY created_at DESC LIMIT 1",
                    (session_id, doc_type),
                ).fetchone()["id"]
                self._connection.execute(
                    "DELETE FROM chunks WHERE session_id = ? AND doc_type = ? AND doc_id != ?",
                    (session_id, doc_type, keep),
                )
                self._connection.execute(
                    "DELETE FROM documents WHERE session_id = ? AND doc_type = ? AND id != ?",
                    (session_id, doc_type, keep),
                )
                logger.info("Kept only the newest %s for session %s", doc_type, session_id)

            self._connection.commit()

    # -- low level ---------------------------------------------------------
    def _execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        with self._lock:
            cursor = self._connection.execute(sql, params)
            self._connection.commit()
            return cursor

    def _query(self, sql: str, params: tuple = ()) -> List[sqlite3.Row]:
        with self._lock:
            return self._connection.execute(sql, params).fetchall()

    # -- sessions ----------------------------------------------------------
    def create_session(self) -> str:
        session_id = uuid.uuid4().hex[:16]
        now = _now()
        self._execute(
            "INSERT INTO sessions (id, created_at, updated_at) VALUES (?, ?, ?)",
            (session_id, now, now),
        )
        logger.info("Created session %s", session_id)
        return session_id

    def session_exists(self, session_id: str) -> bool:
        return bool(self._query("SELECT 1 FROM sessions WHERE id = ?", (session_id,)))

    def require_session(self, session_id: str) -> None:
        if not self.session_exists(session_id):
            raise SessionNotFound()

    def touch_session(self, session_id: str) -> None:
        self._execute("UPDATE sessions SET updated_at = ? WHERE id = ?", (_now(), session_id))

    def delete_session(self, session_id: str) -> None:
        self._execute("DELETE FROM chat_messages WHERE session_id = ?", (session_id,))
        self._execute("DELETE FROM analyses WHERE session_id = ?", (session_id,))
        self._execute("DELETE FROM chunks WHERE session_id = ?", (session_id,))
        self._execute("DELETE FROM documents WHERE session_id = ?", (session_id,))
        self._execute("DELETE FROM sessions WHERE id = ?", (session_id,))

    def expired_session_ids(self) -> List[str]:
        hours = self._settings.session_ttl_hours
        if hours <= 0:
            return []
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        rows = self._query("SELECT id FROM sessions WHERE updated_at < ?", (cutoff,))
        return [row["id"] for row in rows]

    # -- documents ---------------------------------------------------------
    def save_document(
        self,
        *,
        session_id: str,
        doc_id: str,
        doc_type: str,
        name: str,
        source_format: str,
        page_count: int,
        char_count: int,
        chunk_count: int,
        sections: List[str],
        text: str,
    ) -> None:
        self._execute(
            """
            INSERT OR REPLACE INTO documents
                (id, session_id, doc_type, name, source_format, page_count,
                 char_count, chunk_count, sections, text, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                doc_id, session_id, doc_type, name, source_format, page_count,
                char_count, chunk_count, json.dumps(sections), text, _now(),
            ),
        )
        self.touch_session(session_id)

    @staticmethod
    def _hydrate(row: Any) -> Dict[str, Any]:
        item = dict(row)
        item["sections"] = json.loads(item["sections"])
        return item

    def get_document(self, session_id: str, doc_type: str) -> Optional[Dict[str, Any]]:
        """The session's resume or job description."""
        rows = self._query(
            "SELECT * FROM documents WHERE session_id = ? AND doc_type = ? "
            "ORDER BY created_at DESC LIMIT 1",
            (session_id, doc_type),
        )
        return self._hydrate(rows[0]) if rows else None

    def list_documents(self, session_id: str) -> List[Dict[str, Any]]:
        rows = self._query(
            "SELECT * FROM documents WHERE session_id = ? ORDER BY created_at", (session_id,)
        )
        return [self._hydrate(row) for row in rows]

    def delete_documents_of_type(self, session_id: str, doc_type: str) -> List[str]:
        """Delete previous documents of this type. Returns their ids."""
        rows = self._query(
            "SELECT id FROM documents WHERE session_id = ? AND doc_type = ?",
            (session_id, doc_type),
        )
        doc_ids = [row["id"] for row in rows]
        self._execute(
            "DELETE FROM chunks WHERE session_id = ? AND doc_type = ?", (session_id, doc_type)
        )
        self._execute(
            "DELETE FROM documents WHERE session_id = ? AND doc_type = ?", (session_id, doc_type)
        )
        return doc_ids

    # -- chunks ------------------------------------------------------------
    def save_chunks(self, session_id: str, chunks: List[Any]) -> None:
        rows = [
            (
                chunk.chunk_id, session_id, chunk.doc_id, chunk.doc_type, chunk.doc_name,
                chunk.section, chunk.page, chunk.chunk_index, chunk.char_start,
                chunk.char_end, chunk.text,
            )
            for chunk in chunks
        ]
        with self._lock:
            self._connection.executemany(
                """
                INSERT OR REPLACE INTO chunks
                    (chunk_id, session_id, doc_id, doc_type, doc_name, section,
                     page, chunk_index, char_start, char_end, text)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            self._connection.commit()

    def get_chunk(self, session_id: str, chunk_id: str) -> Optional[Dict[str, Any]]:
        rows = self._query(
            "SELECT * FROM chunks WHERE session_id = ? AND chunk_id = ?", (session_id, chunk_id)
        )
        return dict(rows[0]) if rows else None

    def list_chunks(
        self,
        session_id: str,
        doc_type: Optional[str] = None,
        section: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM chunks WHERE session_id = ?"
        params: List[Any] = [session_id]
        if doc_type:
            sql += " AND doc_type = ?"
            params.append(doc_type)
        if section:
            sql += " AND section = ?"
            params.append(section)
        sql += " ORDER BY doc_type, chunk_index"
        return [dict(row) for row in self._query(sql, tuple(params))]

    def count_chunks(self, session_id: str) -> int:
        rows = self._query(
            "SELECT COUNT(*) AS n FROM chunks WHERE session_id = ?", (session_id,)
        )
        return int(rows[0]["n"]) if rows else 0

    # -- cached analyses ---------------------------------------------------
    def save_analysis(self, session_id: str, kind: str, payload: Dict[str, Any]) -> None:
        self._execute(
            "INSERT OR REPLACE INTO analyses (session_id, kind, payload, created_at) "
            "VALUES (?, ?, ?, ?)",
            (session_id, kind, json.dumps(payload), _now()),
        )
        self.touch_session(session_id)

    def get_analysis(self, session_id: str, kind: str) -> Optional[Dict[str, Any]]:
        rows = self._query(
            "SELECT payload FROM analyses WHERE session_id = ? AND kind = ?", (session_id, kind)
        )
        return json.loads(rows[0]["payload"]) if rows else None

    def list_analysis_kinds(self, session_id: str) -> List[str]:
        rows = self._query("SELECT kind FROM analyses WHERE session_id = ?", (session_id,))
        return [row["kind"] for row in rows]

    def clear_analyses(self, session_id: str, keep: Optional[List[str]] = None) -> None:
        """Invalidate cached analysis after a document changes."""
        if keep:
            placeholders = ",".join("?" for _ in keep)
            self._execute(
                f"DELETE FROM analyses WHERE session_id = ? AND kind NOT IN ({placeholders})",
                tuple([session_id] + keep),
            )
        else:
            self._execute("DELETE FROM analyses WHERE session_id = ?", (session_id,))

    # -- chat --------------------------------------------------------------
    def add_chat_message(
        self, session_id: str, role: str, content: str, sources: Optional[List[Dict]] = None
    ) -> None:
        self._execute(
            "INSERT INTO chat_messages (session_id, role, content, sources, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (session_id, role, content, json.dumps(sources or []), _now()),
        )
        self.touch_session(session_id)

    def get_chat_history(self, session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        rows = self._query(
            "SELECT * FROM chat_messages WHERE session_id = ? ORDER BY id DESC LIMIT ?",
            (session_id, limit),
        )
        messages = []
        for row in reversed(rows):
            item = dict(row)
            item["sources"] = json.loads(item["sources"])
            messages.append(item)
        return messages

    def clear_chat(self, session_id: str) -> None:
        self._execute("DELETE FROM chat_messages WHERE session_id = ?", (session_id,))

    def close(self) -> None:
        with self._lock:
            self._connection.close()


# --------------------------------------------------------------------------
# Singleton
# --------------------------------------------------------------------------
_store: Optional[Store] = None
_lock = threading.Lock()


def get_store(settings: Settings) -> Store:
    global _store
    if _store is None:
        with _lock:
            if _store is None:
                _store = Store(settings)
    return _store
