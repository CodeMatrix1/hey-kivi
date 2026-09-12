"""SQLite store for raw interactions and dictation history."""

from __future__ import annotations

import sqlite3
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from hindsight_pipeline_2.kivi.models import DictationRecord


_SOURCE_DICTATION = re.compile(r"\[source_dictation_id=([^\s\]]+)")

def sanitize_fts_query(text_query: str) -> str:
    """Return literal-only FTS5 terms; never accept user FTS syntax."""
    # Drop column selectors before tokenizing (for example, ``body:payment``).
    without_columns = re.sub(r"\b[\w]+\s*:", " ", text_query)
    operators = {"and", "or", "not", "near"}
    terms = [
        token
        for token in re.findall(r"\w+", without_columns, flags=re.UNICODE)
        if token.casefold() not in operators
    ]
    # Quoting every token gives FTS only literal phrases/terms, not operators.
    return " ".join(f'"{term.replace(chr(34), chr(34) * 2)}"' for term in terms)


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def _dictations_table_needs_composite_pk_migration(conn: sqlite3.Connection) -> bool:
    """True when dictations still uses a global ``id`` primary key (legacy schema)."""
    rows = conn.execute("PRAGMA table_info(dictations)").fetchall()
    if not rows:
        return False
    pk_cols = sorted((int(row[5]), str(row[1])) for row in rows if int(row[5]) > 0)
    return pk_cols == [(1, "id")]


def _dictations_create_sql() -> str:
    return """
        CREATE TABLE IF NOT EXISTS dictations (
            user_id TEXT NOT NULL,
            id TEXT NOT NULL,
            asr TEXT NOT NULL,
            formatted TEXT NOT NULL,
            created_at TEXT NOT NULL,
            extra_json TEXT DEFAULT '{}',
            PRIMARY KEY (user_id, id)
        );
        CREATE INDEX IF NOT EXISTS idx_dict_user_time
            ON dictations(user_id, created_at);
    """


def _row_to_record(row: sqlite3.Row | dict[str, Any]) -> DictationRecord:
    data = dict(row)
    return DictationRecord(
        id=str(data["id"]),
        user_id=str(data["user_id"]),
        asr=str(data["asr"]),
        formatted=str(data["formatted"]),
        created_at=str(data["created_at"]),
    )


class DictationStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_schema()

    def _init_schema(self) -> None:
        with _connect(self.db_path) as conn:
            conn.executescript(
                _dictations_create_sql()
                + """
                CREATE TABLE IF NOT EXISTS corpus_ingestions (
                    user_id TEXT NOT NULL,
                    dictation_id TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    memory_id TEXT,
                    retained_at TEXT NOT NULL,
                    PRIMARY KEY (user_id, dictation_id)
                );
                CREATE TABLE IF NOT EXISTS interactions (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )
            self._migrate_drop_app_topic_channel(conn)
            self._migrate_composite_primary_key(conn)
            self._init_fts(conn)

    def _init_fts(self, conn: sqlite3.Connection) -> None:
        """Install the external-content FTS index and one-time backfill it."""
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='dictations_fts'"
        ).fetchone()
        if not exists:
            try:
                conn.execute(
                    """
                    CREATE VIRTUAL TABLE dictations_fts USING fts5(
                        body,
                        content='dictations',
                        content_rowid='rowid',
                        tokenize='unicode61'
                    )
                    """
                )
            except sqlite3.OperationalError as exc:
                raise RuntimeError("SQLite FTS5 is required for dictation search") from exc
            # Existing databases receive one backfill at the time the index is added.
            conn.execute(
                """
                INSERT INTO dictations_fts(rowid, body)
                SELECT rowid, COALESCE(formatted, '') || ' ' || COALESCE(asr, '')
                FROM dictations
                """
            )
        conn.execute(
            """
            CREATE TRIGGER IF NOT EXISTS dictations_fts_insert
            AFTER INSERT ON dictations BEGIN
                INSERT INTO dictations_fts(rowid, body)
                VALUES (new.rowid, COALESCE(new.formatted, '') || ' ' || COALESCE(new.asr, ''));
            END
            """
        )

    def _migrate_drop_app_topic_channel(self, conn: sqlite3.Connection) -> None:
        """Rebuild dictations if an older schema still has app/topic/channel."""
        cols = {
            r[1]
            for r in conn.execute("PRAGMA table_info(dictations)").fetchall()
        }
        if not cols.intersection({"app", "topic", "channel"}):
            return
        conn.execute("DROP TRIGGER IF EXISTS dictations_fts_insert")
        conn.execute("DROP TABLE IF EXISTS dictations_fts")
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS dictations_new (
                user_id TEXT NOT NULL,
                id TEXT NOT NULL,
                asr TEXT NOT NULL,
                formatted TEXT NOT NULL,
                created_at TEXT NOT NULL,
                extra_json TEXT DEFAULT '{}',
                PRIMARY KEY (user_id, id)
            );
            INSERT INTO dictations_new (user_id, id, asr, formatted, created_at, extra_json)
            SELECT user_id, id, asr, formatted, created_at,
                   COALESCE(extra_json, '{}')
            FROM dictations;
            DROP TABLE dictations;
            ALTER TABLE dictations_new RENAME TO dictations;
            CREATE INDEX IF NOT EXISTS idx_dict_user_time
                ON dictations(user_id, created_at);
            """
        )

    def _migrate_composite_primary_key(self, conn: sqlite3.Connection) -> None:
        """Scope dictation ids per user instead of globally unique ids."""
        if not _dictations_table_needs_composite_pk_migration(conn):
            return
        conn.execute("DROP TRIGGER IF EXISTS dictations_fts_insert")
        conn.execute("DROP TABLE IF EXISTS dictations_fts")
        conn.executescript(
            """
            CREATE TABLE dictations_new (
                user_id TEXT NOT NULL,
                id TEXT NOT NULL,
                asr TEXT NOT NULL,
                formatted TEXT NOT NULL,
                created_at TEXT NOT NULL,
                extra_json TEXT DEFAULT '{}',
                PRIMARY KEY (user_id, id)
            );
            INSERT INTO dictations_new (user_id, id, asr, formatted, created_at, extra_json)
            SELECT user_id, id, asr, formatted, created_at,
                   COALESCE(extra_json, '{}')
            FROM dictations;
            DROP TABLE dictations;
            ALTER TABLE dictations_new RENAME TO dictations;
            CREATE INDEX IF NOT EXISTS idx_dict_user_time
                ON dictations(user_id, created_at);
            """
        )

    def add_dictation(self, record: DictationRecord) -> DictationRecord:
        with _connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO dictations
                (id, user_id, asr, formatted, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    record.id,
                    record.user_id,
                    record.asr,
                    record.formatted,
                    record.created_at,
                ),
            )
        return record

    def get(self, user_id: str, dictation_id: str) -> DictationRecord | None:
        with _connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT id, user_id, asr, formatted, created_at FROM dictations WHERE user_id=? AND id=?",
                (user_id, dictation_id),
            ).fetchone()
        if not row:
            return None
        return _row_to_record(row)

    def resolve_source_dictation(
        self,
        user_id: str,
        text: str,
        *,
        memory_id: str | None = None,
    ) -> str | None:
        """Map a Hindsight recall hit back to a corpus/chat dictation id when possible."""
        if memory_id:
            with _connect(self.db_path) as conn:
                row = conn.execute(
                    """
                    SELECT dictation_id FROM corpus_ingestions
                    WHERE user_id=? AND memory_id=?
                    """,
                    (user_id, memory_id),
                ).fetchone()
                if row:
                    return str(row["dictation_id"])
            if memory_id.startswith("dict_"):
                candidate = memory_id[5:]
                if self.get(user_id, candidate) is not None:
                    return candidate

        match = _SOURCE_DICTATION.search(text or "")
        if match:
            return match.group(1)
        return None

    def ingestion_for(self, user_id: str, dictation_id: str) -> dict[str, str] | None:
        """Return the successful Hindsight-ingestion marker for a dictation."""
        with _connect(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT content_hash, memory_id, retained_at
                FROM corpus_ingestions
                WHERE user_id=? AND dictation_id=?
                """,
                (user_id, dictation_id),
            ).fetchone()
        return dict(row) if row else None

    def mark_ingested(
        self,
        user_id: str,
        dictation_id: str,
        *,
        content_hash: str,
        memory_id: str | None,
    ) -> None:
        """Persist a marker only after a corpus retain completes successfully."""
        with _connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO corpus_ingestions
                (user_id, dictation_id, content_hash, memory_id, retained_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    dictation_id,
                    content_hash,
                    memory_id,
                    datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                ),
            )

    def count_for_user(self, user_id: str) -> int:
        with _connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM dictations WHERE user_id=?",
                (user_id,),
            ).fetchone()
        return int(row[0]) if row else 0

    def list_for_user(self, user_id: str, limit: int = 100) -> list[DictationRecord]:
        with _connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT id, user_id, asr, formatted, created_at
                FROM dictations WHERE user_id=?
                ORDER BY created_at DESC LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()
        return [_row_to_record(r) for r in rows]

    def list_by_id_prefix(self, user_id: str, id_prefix: str) -> list[DictationRecord]:
        with _connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT id, user_id, asr, formatted, created_at
                FROM dictations
                WHERE user_id=? AND id LIKE ?
                ORDER BY created_at ASC
                """,
                (user_id, f"{id_prefix}%"),
            ).fetchall()
        return [_row_to_record(r) for r in rows]

    def find(
        self,
        user_id: str,
        *,
        text_query: str = "",
        date_start: str | None = None,
        date_end: str | None = None,
        limit: int = 8,
    ) -> list[dict[str, Any]]:
        """Deterministic FTS5/date search; this never uses an LLM."""
        if limit <= 0 or (date_start is not None and date_end is not None and date_start >= date_end):
            return []
        fts_query = sanitize_fts_query(text_query)
        has_text = bool(fts_query)
        has_date = bool(date_start or date_end)
        date_sql: list[str] = []
        date_values: list[Any] = []
        if date_start is not None:
            date_sql.append("d.created_at >= ?")
            date_values.append(date_start)
        if date_end is not None:
            date_sql.append("d.created_at < ?")
            date_values.append(date_end)
        date_clause = (" AND " + " AND ".join(date_sql)) if date_sql else ""

        with _connect(self.db_path) as conn:
            if has_text:
                rows = conn.execute(
                    """
                    SELECT d.id, d.created_at, d.formatted, bm25(dictations_fts) AS bm25_raw
                    FROM dictations_fts
                    JOIN dictations AS d ON d.rowid = dictations_fts.rowid
                    WHERE dictations_fts MATCH ? AND d.user_id=?
                    """
                    + date_clause
                    + " ORDER BY bm25(dictations_fts), d.created_at DESC, d.id LIMIT ?",
                    [fts_query, user_id, *date_values, limit],
                ).fetchall()
            elif has_date:
                rows = conn.execute(
                    """
                    SELECT d.id, d.created_at, d.formatted
                    FROM dictations AS d WHERE d.user_id=?
                    """
                    + date_clause
                    + " ORDER BY d.created_at DESC, d.id DESC LIMIT ?",
                    [user_id, *date_values, limit],
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT d.id, d.created_at, d.formatted
                    FROM dictations AS d WHERE d.user_id=?
                    ORDER BY d.created_at DESC, d.id DESC LIMIT ?
                    """,
                    (user_id, min(3, limit)),
                ).fetchall()

        candidates: list[dict[str, Any]] = []
        for row in rows:
            if has_text:
                text_component = min(0.75, max(0.25, 0.25 + 0.50 * (1 / (1 + max(0, row["bm25_raw"])))) )
                score = min(1.0, text_component + 0.35) if has_date else text_component
                evidence = ["fts", "date_window"] if has_date else ["fts"]
            elif has_date:
                score, evidence = 0.35, ["date_window"]
            else:
                score, evidence = 0.2, ["recency"]
            candidates.append({
                "id": str(row["id"]),
                "score": round(score, 3),
                "evidence": evidence,
                "created_at": str(row["created_at"]),
                "formatted_preview": str(row["formatted"])[:180],
            })
        return candidates

    def log_interaction(self, user_id: str, role: str, content: str) -> str:
        iid = f"i_{uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        with _connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO interactions (id, user_id, role, content, created_at) VALUES (?,?,?,?,?)",
                (iid, user_id, role, content, now),
            )
        return iid

    def clear_user(self, user_id: str) -> None:
        with _connect(self.db_path) as conn:
            try:
                conn.execute(
                    "DELETE FROM dictations_fts WHERE rowid IN (SELECT rowid FROM dictations WHERE user_id=?)",
                    (user_id,),
                )
            except sqlite3.OperationalError:
                # FTS5 body column may not exist in pre-FTS5 databases; ignore.
                pass
            conn.execute("DELETE FROM dictations WHERE user_id=?", (user_id,))
            conn.execute("DELETE FROM interactions WHERE user_id=?", (user_id,))
            conn.execute("DELETE FROM corpus_ingestions WHERE user_id=?", (user_id,))
