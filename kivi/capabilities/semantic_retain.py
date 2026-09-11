"""Semantic retain: push canonical user text into Hindsight."""

from __future__ import annotations

from typing import Any

from hindsight_pipeline_2.kivi.models import DecisionTrace


def run_semantic_retain(
    *,
    memory: Any,
    user_id: str,
    canonical: str,
    trace: DecisionTrace,
    source_dictation_id: str | None = None,
    created_at: str | None = None,
) -> None:
    """Retain canonicalized message for Fact/Preference/Episode extraction."""
    content = canonical
    metadata: dict[str, Any] = {}
    if source_dictation_id:
        header = (
            f"[source_dictation_id={source_dictation_id} "
            f"created_at={created_at or ''} user_id={user_id}]"
        )
        content = f"{header}\n{canonical}"
        metadata = {
            "dictation_id": source_dictation_id,
            "created_at": created_at,
            "id": f"dict_{source_dictation_id}",
        }
    try:
        memory.retain(user_id, content, metadata=metadata or None)
        trace.semantic_retain = True
        preview = canonical if len(canonical) <= 240 else canonical[:237] + "…"
        trace.semantic_retain_preview = preview
    except Exception as exc:  # noqa: BLE001
        trace.semantic_retain = False
        trace.reason = f"semantic_retain_failed: {exc}"
