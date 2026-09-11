"""In-memory memory backend for offline tests (not production)."""

from __future__ import annotations

import re
from typing import Any

from hindsight_pipeline_2.kivi.models import MemoryBase


def _token_match(token: str, text: str) -> bool:
    if re.search(rf"\b{re.escape(token)}\b", text):
        return True
    root = re.sub(r"(ing|ed|es|s)$", "", token)
    return len(root) >= 5 and root in text


class StubMemory:
    """Deterministic retain/recall for pytest without Docker or Hindsight."""

    backend_name = "stub"

    def __init__(self) -> None:
        self._banks: dict[str, list[dict[str, Any]]] = {}

    def retain(
        self,
        user_id: str,
        content: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        items = self._banks.setdefault(user_id, [])
        mid = (metadata or {}).get("id") or f"mem_{len(items)}"
        items.append(
            {
                "id": mid,
                "text": content,
                "metadata": metadata or {},
            }
        )
        return {"bank_id": f"stub_{user_id}", "id": mid, "metadata": metadata or {}}

    def recall(self, user_id: str, query: str, *, limit: int = 12) -> list[dict[str, Any]]:
        items = self._banks.get(user_id, [])
        if not query.strip():
            return items[:limit]
        stop = {
            "a", "an", "the", "for", "what", "have", "i", "been", "on", "in", "to",
            "my", "me", "is", "are", "do", "did", "you", "that", "this", "with",
            "how", "should", "spell", "would", "could", "kind", "about",
            "based", "told", "and", "ones", "actually", "only",
            "trip", "trips", "considering", "itinerary", "suit", "month", "next", "short",
            "confirm", "book",
        }
        q = [tok for tok in re.findall(r"\w+", query.lower()) if tok not in stop and len(tok) > 2]
        if not q:
            return []
        scored: list[tuple[float, dict[str, Any]]] = []
        for item in items:
            text = str(item.get("text") or "").lower()
            hits = sum(1 for tok in q if _token_match(tok, text))
            if hits:
                scored.append((hits / len(q), item))
        scored.sort(key=lambda pair: pair[0], reverse=True)

        merged: list[dict[str, Any]] = []
        seen: set[str] = set()
        body_counts: dict[str, int] = {}

        def _body_key(item: dict[str, Any]) -> str:
            text = str(item.get("text") or "")
            if "\n" in text:
                text = text.split("\n", 1)[-1]
            return text[:72].casefold()

        def _try_add(item: dict[str, Any]) -> bool:
            item_id = str(item.get("id") or "")
            if item_id in seen:
                return False
            key = _body_key(item)
            if body_counts.get(key, 0) >= 2:
                return False
            seen.add(item_id)
            body_counts[key] = body_counts.get(key, 0) + 1
            merged.append(item)
            return True

        for tok in q:
            best: tuple[float, dict[str, Any]] | None = None
            for score, item in scored:
                text = str(item.get("text") or "").lower()
                if not _token_match(tok, text):
                    continue
                if best is None or score > best[0]:
                    best = (score, item)
            if best is not None:
                _try_add(best[1])
        for _, item in scored:
            if len(merged) >= limit:
                break
            _try_add(item)
        if not merged and items:
            return items[:limit]
        return merged[:limit]

    def list_memories(self, user_id: str) -> list[dict[str, Any]]:
        return self.recall(user_id, "", limit=50)

    def count_memories(self, user_id: str) -> int:
        return len(self._banks.get(user_id, []))

    def reset(self, user_id: str) -> dict[str, Any]:
        self._banks.pop(user_id, None)
        return {"bank_id": f"stub_{user_id}", "cleared": True}

    def close(self) -> None:
        return None


def retain_typed(backend: Any, user_id: str, memory: MemoryBase) -> dict[str, Any]:
    return backend.retain(user_id, memory.to_retain_payload(), metadata=memory.model_dump())
