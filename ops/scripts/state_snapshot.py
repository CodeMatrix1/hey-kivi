"""Quick stdout inspect of SQLite + Hindsight state (no report file)."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

from hindsight_pipeline_2.kivi.config import Settings
from hindsight_pipeline_2.kivi.storage.dictation_store import DictationStore
from hindsight_pipeline_2.kivi.memory.hindsight_adapter import get_memory_backend
from hindsight_pipeline_2.kivi.instrumentation import sqlite_counts
from hindsight_pipeline_2.kivi.storage.lexical_store import LexicalStore


def snapshot(user_id: str, settings: Settings | None = None) -> dict:
    cfg = settings or Settings.from_env()
    store = DictationStore(cfg.db_path)
    lex = LexicalStore(cfg.db_path)
    out: dict = {
        "user_id": user_id,
        "db_path": str(cfg.db_path),
        "counts": sqlite_counts(cfg.db_path, user_id),
        "dictations": [r.model_dump() for r in store.list_for_user(user_id, limit=20)],
        "lexical_mappings": [m.to_dict() for m in lex.list_active(user_id)],
        "ingestions": [],
        "memories": [],
    }
    conn = sqlite3.connect(str(cfg.db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT dictation_id, content_hash, memory_id, retained_at "
            "FROM corpus_ingestions WHERE user_id=? ORDER BY retained_at DESC LIMIT 20",
            (user_id,),
        ).fetchall()
        out["ingestions"] = [dict(r) for r in rows]
    finally:
        conn.close()
    try:
        memory = get_memory_backend(cfg)
        out["memories"] = memory.list_memories(user_id)[:20]
        close = getattr(memory, "close", None)
        if callable(close):
            close()
    except Exception as exc:  # noqa: BLE001
        out["memory_error"] = str(exc)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Snapshot SQLite + Hindsight state for a user")
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--db-path", type=Path, default=None)
    args = parser.parse_args(argv)
    settings = Settings.from_env()
    if args.db_path:
        settings = Settings(
            hindsight_base_url=settings.hindsight_base_url,
            hindsight_api_key=settings.hindsight_api_key,
            bank_prefix=settings.bank_prefix,
            memory_backend=settings.memory_backend,
            llm_provider=settings.llm_provider,
            db_path=args.db_path,
            recall_budget=settings.recall_budget,
        )
    print(json.dumps(snapshot(args.user_id.strip(), settings=settings), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
