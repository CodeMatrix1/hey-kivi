"""Hey Kivi tools: find_dictations + polish_dictation."""

from __future__ import annotations

from typing import Any

from hindsight_pipeline_2.kivi.config import POLISH_SYSTEM
from hindsight_pipeline_2.kivi.corpus.text_cleanup import strip_corpus_metadata_noise
from hindsight_pipeline_2.kivi.storage.dictation_store import DictationStore
from hindsight_pipeline_2.kivi.storage.lexical import resolve_lexical_mappings
from hindsight_pipeline_2.kivi.storage.lexical_store import LexicalStore


def find_dictations(
    store: DictationStore,
    user_id: str,
    *,
    text_query: str = "",
    date_start: str | None = None,
    date_end: str | None = None,
    limit: int = 8,
) -> list[dict[str, Any]]:
    return store.find(
        user_id,
        text_query=text_query,
        date_start=date_start,
        date_end=date_end,
        limit=limit,
    )


def polish_dictation(
    store: DictationStore,
    memory_backend: Any,
    user_id: str,
    dictation_id: str,
    occasion: str,
    *,
    text_llm: Any | None = None,
    lexical_store: LexicalStore | None = None,
) -> dict[str, Any]:
    """load → optional Hindsight context → LLM polish → SQLite lexical resolve."""
    rec = store.get(user_id, dictation_id)
    if rec is None:
        return {"ok": False, "error": "dictation_not_found"}

    source_text = strip_corpus_metadata_noise(rec.formatted)
    retrieval_query = f"{occasion} {source_text}"
    recalled: list[dict[str, Any]] = []
    backend_name = getattr(memory_backend, "backend_name", "unknown")
    if memory_backend is not None:
        recalled = memory_backend.recall(user_id, retrieval_query, limit=12)

    context_blob = "\n".join(f"- {r.get('text', '')[:200]}" for r in recalled[:6]) or "(none)"
    polished = source_text
    llm_source = "skipped"
    llm_output: str | None = None
    if text_llm is not None:
        user = (
            f"Occasion: {occasion}\n"
            f"Related memories (context only):\n{context_blob}\n\n"
            f"Transcript:\n{source_text}"
        )
        try:
            polished = text_llm(POLISH_SYSTEM, user).strip()
            llm_source = "llm"
            llm_output = polished
        except Exception as exc:  # noqa: BLE001
            polished = source_text
            llm_source = "fallback"
            llm_output = f"error: {exc}"

    applied: list[dict[str, str]] = []
    final = polished
    # Preference-teaching rows (lexical_*) define mappings; don't rewrite themselves.
    if lexical_store is not None and not str(dictation_id).startswith("lexical_"):
        final, mappings = resolve_lexical_mappings(user_id, polished, lexical_store)
        applied = [
            {"observed": m.alias, "preferred": m.canonical, "kind": m.kind} for m in mappings
        ]

    return {
        "ok": True,
        "dictation_id": dictation_id,
        "polished_text": final,
        "original_formatted": rec.formatted,
        "retrieved": recalled,
        "applied_preferences": applied,
        "retrieval_backend": backend_name,
        "retrieval_query": retrieval_query,
        "created_at": rec.created_at,
        "llm_source": llm_source,
        "llm_output": llm_output,
    }
