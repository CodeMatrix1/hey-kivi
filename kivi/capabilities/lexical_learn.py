"""Lexical learn: extract → validate → upsert → canonicalize."""

from __future__ import annotations

from typing import Any

from hindsight_pipeline_2.kivi.capabilities.trace_utils import record_llm
from hindsight_pipeline_2.kivi.storage.lexical import resolve_lexical_mappings
from hindsight_pipeline_2.kivi.lexical.lexical_extract import (
    extract_lexical_mappings,
    validate_lexical_extraction,
)
from hindsight_pipeline_2.kivi.storage.lexical_store import LexicalStore
from hindsight_pipeline_2.kivi.models import DecisionTrace


def run_lexical_learn(
    *,
    user_id: str,
    raw: str,
    interaction_id: str,
    lexical_store: LexicalStore,
    lexical_llm: Any,
    trace: DecisionTrace,
) -> tuple[str, list[str]]:
    """Learn mappings from this message and return (canonical_text, reply_parts)."""
    parts: list[str] = []
    lex_meta: dict[str, Any] = {}
    proposed = extract_lexical_mappings(raw, llm=lexical_llm, meta=lex_meta)
    record_llm(
        trace,
        "lexical_extract",
        source=str(lex_meta.get("source") or "skipped"),
        output=lex_meta.get("output"),
    )
    validated = validate_lexical_extraction(raw, proposed)
    validated_set = {(m.alias, m.canonical, m.kind) for m in validated.mappings}
    for m in proposed.mappings:
        key = (m.alias, m.canonical, m.kind)
        if key not in validated_set:
            trace.memories_ignored.append(
                {
                    "text": f"{m.alias} → {m.canonical}",
                    "reason": "lexical_validation_failed",
                    "kind": m.kind,
                }
            )
    for m in validated.mappings:
        result = lexical_store.upsert_mapping(
            user_id, m, source_interaction_id=interaction_id
        )
        trace.memories_retained.append(
            {
                "type": "LexicalMapping",
                "alias": m.alias,
                "canonical": m.canonical,
                "kind": m.kind,
                "id": result["id"],
                "text": f"{m.alias} → {m.canonical}",
            }
        )
        if result.get("superseded"):
            trace.memories_updated.extend(result["superseded"])
        parts.append(f"Got it — I'll use '{m.canonical}' instead of '{m.alias}'.")

    canonical, applied = resolve_lexical_mappings(user_id, raw, lexical_store)
    trace.canonicalized_message = canonical
    if applied:
        trace.applied_preferences.extend(
            {"observed": m.alias, "preferred": m.canonical, "kind": m.kind} for m in applied
        )
    return canonical, parts
