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
    source_interaction_id: str | None = None,
    created_at: str | None = None,
    kivi_chat: bool = False,
) -> None:
    """Retain canonicalized message for Fact/Preference/Episode extraction."""
    content = canonical
    metadata: dict[str, Any] = {}
    header_tags: list[str] = []
    if source_dictation_id:
        header_tags.append(f"source_dictation_id={source_dictation_id}")
    if source_interaction_id:
        header_tags.append(f"source_interaction_id={source_interaction_id}")
    if kivi_chat:
        header_tags.append("kivi_chat=true")
    if header_tags:
        header_tags.append(f"created_at={created_at or ''}")
        header_tags.append(f"user_id={user_id}")
        header = f"[{' '.join(header_tags)}]"
        content = f"{header}\n{canonical}"
        if kivi_chat and source_interaction_id:
            metadata = {
                "interaction_id": source_interaction_id,
                "created_at": created_at,
                "id": f"chat_{source_interaction_id}",
                "kivi_chat": True,
            }
        elif source_dictation_id:
            metadata = {
                "dictation_id": source_dictation_id,
                "created_at": created_at,
                "id": f"dict_{source_dictation_id}",
                "kivi_chat": False,
            }
    try:
        memory.retain(user_id, content, metadata=metadata or None)
        trace.semantic_retain = True
        preview = canonical if len(canonical) <= 240 else canonical[:237] + "…"
        trace.semantic_retain_preview = preview
    except Exception as exc:  # noqa: BLE001
        trace.semantic_retain = False
        trace.reason = f"semantic_retain_failed: {exc}"
