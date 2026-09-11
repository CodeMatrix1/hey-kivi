"""Deterministic lexical apply: word-boundary alias → canonical resolution."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from hindsight_pipeline_2.kivi.models import LexicalMapping

if TYPE_CHECKING:
    from hindsight_pipeline_2.kivi.storage.lexical_store import LexicalStore


def _boundary_pattern(target: str) -> re.Pattern[str]:
    escaped = re.escape(target)
    return re.compile(rf"(?<![A-Za-z0-9_]){escaped}(?![A-Za-z0-9_])")


def target_occurs(text: str, target: str) -> bool:
    if not target or target not in text:
        return False
    return _boundary_pattern(target).search(text) is not None


def apply_lexical(text: str, target: str, replacement: str) -> tuple[str, int]:
    if not target_occurs(text, target):
        return text, 0
    return _boundary_pattern(target).subn(replacement, text)


def resolve_lexical_mappings(
    user_id: str,
    text: str,
    store: "LexicalStore",
) -> tuple[str, list[LexicalMapping]]:
    """Apply all active user-scoped mappings (longest alias first)."""
    rows = store.list_active(user_id)
    mappings = [r.to_mapping() for r in rows]
    # Longest alias first to avoid partial overlaps
    mappings.sort(key=lambda m: len(m.alias), reverse=True)
    current = text
    applied: list[LexicalMapping] = []
    seen_aliases: set[str] = set()
    for m in mappings:
        if m.alias in seen_aliases:
            continue
        if m.alias == m.canonical:
            continue
        updated, count = apply_lexical(current, m.alias, m.canonical)
        if count:
            current = updated
            seen_aliases.add(m.alias)
            applied.append(m)
    return current, applied
