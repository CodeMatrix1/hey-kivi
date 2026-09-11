"""User-scoped SQLite store for explicit lexical alias→canonical mappings."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from hindsight_pipeline_2.kivi.storage.dictation_store import _connect
from hindsight_pipeline_2.kivi.models import LexicalKind, LexicalMapping


def normalize_lexical(s: str) -> str:
    return s.casefold().strip()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class LexicalMappingRow:
    id: str
    user_id: str
    alias: str
    canonical: str
    kind: LexicalKind
    active: bool
    created_at: str
    updated_at: str
    source_interaction_id: str | None
    normalized_alias: str
    normalized_canonical: str

    def to_mapping(self) -> LexicalMapping:
        return LexicalMapping(alias=self.alias, canonical=self.canonical, kind=self.kind)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "alias": self.alias,
            "canonical": self.canonical,
            "kind": self.kind,
            "active": self.active,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "source_interaction_id": self.source_interaction_id,
            "normalized_alias": self.normalized_alias,
            "normalized_canonical": self.normalized_canonical,
        }


class LexicalStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_schema()

    def _init_schema(self) -> None:
        with _connect(self.db_path) as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS lexical_mappings (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    alias TEXT NOT NULL,
                    canonical TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    source_interaction_id TEXT,
                    normalized_alias TEXT NOT NULL,
                    normalized_canonical TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_lex_user_active
                    ON lexical_mappings(user_id, active);
                CREATE INDEX IF NOT EXISTS idx_lex_user_norm_alias
                    ON lexical_mappings(user_id, normalized_alias, active);
                """
            )

    def upsert_mapping(
        self,
        user_id: str,
        mapping: LexicalMapping,
        *,
        source_interaction_id: str | None = None,
    ) -> dict[str, Any]:
        """Persist a validated explicit mapping; supersede conflicts for this user only."""
        now = utc_now_iso()
        n_alias = normalize_lexical(mapping.alias)
        n_canon = normalize_lexical(mapping.canonical)
        superseded: list[dict[str, Any]] = []

        with _connect(self.db_path) as conn:
            # Deactivate same normalized_alias with different canonical
            rows = conn.execute(
                """
                SELECT id, alias, canonical FROM lexical_mappings
                WHERE user_id=? AND active=1 AND normalized_alias=?
                """,
                (user_id, n_alias),
            ).fetchall()
            for row in rows:
                if normalize_lexical(row["canonical"]) != n_canon:
                    conn.execute(
                        "UPDATE lexical_mappings SET active=0, updated_at=? WHERE id=?",
                        (now, row["id"]),
                    )
                    superseded.append(
                        {
                            "id": row["id"],
                            "action": "superseded_by_newer",
                            "alias": row["alias"],
                            "canonical": row["canonical"],
                        }
                    )

            # Deactivate explicit reverse: old active alias==new canonical and canonical==new alias
            rev = conn.execute(
                """
                SELECT id, alias, canonical FROM lexical_mappings
                WHERE user_id=? AND active=1
                  AND normalized_alias=? AND normalized_canonical=?
                """,
                (user_id, n_canon, n_alias),
            ).fetchall()
            for row in rev:
                conn.execute(
                    "UPDATE lexical_mappings SET active=0, updated_at=? WHERE id=?",
                    (now, row["id"]),
                )
                superseded.append(
                    {
                        "id": row["id"],
                        "action": "superseded_reverse",
                        "alias": row["alias"],
                        "canonical": row["canonical"],
                    }
                )

            # Reactivate / update existing identical alias+canonical, else insert
            existing = conn.execute(
                """
                SELECT id FROM lexical_mappings
                WHERE user_id=? AND normalized_alias=? AND normalized_canonical=?
                """,
                (user_id, n_alias, n_canon),
            ).fetchone()
            if existing:
                mid = existing["id"]
                conn.execute(
                    """
                    UPDATE lexical_mappings
                    SET alias=?, canonical=?, kind=?, active=1, updated_at=?,
                        source_interaction_id=COALESCE(?, source_interaction_id)
                    WHERE id=?
                    """,
                    (
                        mapping.alias,
                        mapping.canonical,
                        mapping.kind,
                        now,
                        source_interaction_id,
                        mid,
                    ),
                )
            else:
                mid = f"lex_{uuid4().hex[:12]}"
                conn.execute(
                    """
                    INSERT INTO lexical_mappings
                    (id, user_id, alias, canonical, kind, active, created_at, updated_at,
                     source_interaction_id, normalized_alias, normalized_canonical)
                    VALUES (?,?,?,?,?,1,?,?,?,?,?)
                    """,
                    (
                        mid,
                        user_id,
                        mapping.alias,
                        mapping.canonical,
                        mapping.kind,
                        now,
                        now,
                        source_interaction_id,
                        n_alias,
                        n_canon,
                    ),
                )

        return {
            "id": mid,
            "mapping": mapping.model_dump(),
            "superseded": superseded,
        }

    def active_count(self, user_id: str) -> int:
        with _connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM lexical_mappings WHERE user_id=? AND active=1",
                (user_id,),
            ).fetchone()
        return int(row[0]) if row else 0

    def list_active(self, user_id: str) -> list[LexicalMappingRow]:
        with _connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT * FROM lexical_mappings
                WHERE user_id=? AND active=1
                ORDER BY updated_at DESC
                """,
                (user_id,),
            ).fetchall()
        return [_row_to_record(r) for r in rows]

    def clear_user(self, user_id: str) -> None:
        with _connect(self.db_path) as conn:
            conn.execute("DELETE FROM lexical_mappings WHERE user_id=?", (user_id,))


def _row_to_record(row: Any) -> LexicalMappingRow:
    return LexicalMappingRow(
        id=row["id"],
        user_id=row["user_id"],
        alias=row["alias"],
        canonical=row["canonical"],
        kind=row["kind"],
        active=bool(row["active"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        source_interaction_id=row["source_interaction_id"],
        normalized_alias=row["normalized_alias"],
        normalized_canonical=row["normalized_canonical"],
    )
