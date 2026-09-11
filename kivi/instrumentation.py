"""Lightweight timing and DB counters for eval reports."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from hindsight_pipeline_2.kivi.storage.dictation_store import DictationStore
from hindsight_pipeline_2.kivi.storage.lexical_store import LexicalStore


@dataclass
class RunMetrics:
    elapsed_ms: float = 0.0
    llm_call_count: int = 0
    retain_call_count: int = 0
    db_before: dict[str, int] = field(default_factory=dict)
    db_after: dict[str, int] = field(default_factory=dict)
    cost_usd: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "elapsed_ms": round(self.elapsed_ms, 2),
            "llm_call_count": self.llm_call_count,
            "retain_call_count": self.retain_call_count,
            "db_before": self.db_before,
            "db_after": self.db_after,
            "db_delta": {
                key: self.db_after.get(key, 0) - self.db_before.get(key, 0)
                for key in set(self.db_before) | set(self.db_after)
            },
            "cost_usd": self.cost_usd,
        }


class MetricsTimer:
    def __init__(self) -> None:
        self._start = time.perf_counter()

    def elapsed_ms(self) -> float:
        return (time.perf_counter() - self._start) * 1000.0


def sqlite_counts(db_path: Path, user_id: str | None = None) -> dict[str, int]:
    store = DictationStore(db_path)
    lex = LexicalStore(db_path)
    import sqlite3

    conn = sqlite3.connect(str(db_path))
    try:
        if user_id:
            counts = {
                "dictations": store.count_for_user(user_id),
                "lexical_mappings": len(lex.list_active(user_id)),
                "interactions": conn.execute(
                    "SELECT COUNT(*) FROM interactions WHERE user_id=?", (user_id,)
                ).fetchone()[0],
                "corpus_ingestions": conn.execute(
                    "SELECT COUNT(*) FROM corpus_ingestions WHERE user_id=?", (user_id,)
                ).fetchone()[0],
            }
        else:
            counts = {
                "dictations": conn.execute("SELECT COUNT(*) FROM dictations").fetchone()[0],
                "lexical_mappings": conn.execute(
                    "SELECT COUNT(*) FROM lexical_mappings WHERE active=1"
                ).fetchone()[0],
                "interactions": conn.execute("SELECT COUNT(*) FROM interactions").fetchone()[0],
                "corpus_ingestions": conn.execute(
                    "SELECT COUNT(*) FROM corpus_ingestions"
                ).fetchone()[0],
            }
    finally:
        conn.close()
    return counts


def count_llm_calls(trace: dict[str, Any]) -> int:
    return len(trace.get("llm_calls") or [])


def count_retain_calls(trace: dict[str, Any]) -> int:
    return 1 if trace.get("semantic_retain") else 0


def estimate_turn_cost_usd(llm_call_count: int, retain_call_count: int) -> float:
    """Rough per-turn cost; set KIVI_ESTIMATED_*_COST_USD env vars to estimate."""
    per_llm = float(os.getenv("KIVI_ESTIMATED_LLM_COST_USD", "0"))
    per_retain = float(os.getenv("KIVI_ESTIMATED_RETAIN_COST_USD", "0"))
    return round(llm_call_count * per_llm + retain_call_count * per_retain, 4)


def build_turn_metrics(
    *,
    trace: dict[str, Any],
    db_before: dict[str, int],
    db_after: dict[str, int],
    elapsed_ms: float,
) -> dict[str, Any]:
    """Server-side metrics for a single /chat turn."""
    llm_call_count = count_llm_calls(trace)
    retain_call_count = count_retain_calls(trace)
    metrics = RunMetrics(
        elapsed_ms=elapsed_ms,
        llm_call_count=llm_call_count,
        retain_call_count=retain_call_count,
        db_before=db_before,
        db_after=db_after,
        cost_usd=estimate_turn_cost_usd(llm_call_count, retain_call_count),
    )
    return metrics.to_dict()
