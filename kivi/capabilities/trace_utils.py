"""Shared helpers for writing the decision trace."""

from __future__ import annotations

import re
from typing import Any

from hindsight_pipeline_2.kivi.models import DecisionTrace

_MEMORY_HEADER = re.compile(
    r"\[KIVI_MEMORY[^\]]*type=(?P<type>\w+)[^\]]*\]\s*",
    re.I,
)
_SOURCE_DICTATION = re.compile(r"\[source_dictation_id=([^\s\]]+)")


def memory_card(
    item: dict[str, Any],
    *,
    store: Any | None = None,
    user_id: str | None = None,
) -> dict[str, Any]:
    """Normalize a recall hit for the decision trace (type + clean text)."""
    raw_text = str(item.get("text") or "")
    mem_type = None
    source_dictation_id: str | None = None
    meta = item.get("metadata") or {}
    if isinstance(meta, dict):
        if meta.get("type"):
            mem_type = str(meta["type"])
        if meta.get("dictation_id"):
            source_dictation_id = str(meta["dictation_id"])
    src_match = _SOURCE_DICTATION.search(raw_text)
    if src_match:
        source_dictation_id = source_dictation_id or src_match.group(1)
    if not source_dictation_id and store is not None and user_id:
        resolve = getattr(store, "resolve_source_dictation", None)
        if callable(resolve):
            source_dictation_id = resolve(
                user_id,
                raw_text,
                memory_id=str(item.get("id") or "") or None,
            )
    m = _MEMORY_HEADER.search(raw_text)
    if m:
        mem_type = mem_type or m.group("type")
        text = _MEMORY_HEADER.sub("", raw_text, count=1).strip()
    elif src_match:
        parts = raw_text.split("\n", 1)
        text = parts[1].strip() if len(parts) > 1 else raw_text.strip()
    else:
        text = raw_text.strip()
    card: dict[str, Any] = {
        "id": item.get("id"),
        "type": mem_type or "Memory",
        "text": text[:400],
    }
    if source_dictation_id:
        card["source_dictation_id"] = source_dictation_id
    return card


def clip(value: Any, limit: int = 1200) -> Any:
    """Keep trace payloads readable."""
    if isinstance(value, str):
        return value if len(value) <= limit else value[: limit - 1] + "…"
    if isinstance(value, dict):
        return {k: clip(v, limit) for k, v in value.items()}
    if isinstance(value, list):
        return [clip(v, limit) for v in value[:20]]
    return value


def record_llm(
    trace: DecisionTrace,
    step: str,
    *,
    source: str,
    output: Any,
) -> None:
    trace.llm_calls.append({"step": step, "source": source, "output": clip(output)})
