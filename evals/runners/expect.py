"""Shared case loading and trace expectation checks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_cases(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise ValueError(f"{path.name} must be a JSON list")
    return data


def _contains_any(hay: str, needles: list[str]) -> bool:
    low = hay.lower()
    return any(n.lower() in low for n in needles)


def check_expect(
    expect: dict[str, Any],
    *,
    reply: str,
    trace: dict[str, Any],
    seeded_memory_texts: list[str],
) -> list[str]:
    """Return list of failure messages (empty = pass)."""
    fails: list[str] = []

    decision = trace.get("decision")
    if "decision" in expect and decision != expect["decision"]:
        fails.append(f"decision={decision!r} expected {expect['decision']!r}")
    if "decision_in" in expect and decision not in expect["decision_in"]:
        fails.append(f"decision={decision!r} not in {expect['decision_in']}")

    tools = trace.get("tools_used") or []
    for t in expect.get("tools_include") or []:
        if t not in tools:
            fails.append(f"missing tool {t!r}; got {tools}")
    for t in expect.get("forbid_tools") or []:
        if t in tools:
            fails.append(f"forbidden tool {t!r} was used")

    rb = trace.get("retrieval_backend")
    if "retrieval_backend_in" in expect and rb not in expect["retrieval_backend_in"]:
        fails.append(f"retrieval_backend={rb!r} not in {expect['retrieval_backend_in']}")

    considered = trace.get("memories_considered") or []
    if expect.get("memories_considered_min") is not None:
        if len(considered) < int(expect["memories_considered_min"]):
            fails.append(
                f"memories_considered={len(considered)} < {expect['memories_considered_min']}"
            )

    retained = trace.get("memories_retained") or []
    if expect.get("memories_retained_min") is not None:
        if len(retained) < int(expect["memories_retained_min"]):
            fails.append(f"memories_retained={len(retained)} < {expect['memories_retained_min']}")
    if expect.get("memories_retained_max") is not None:
        if len(retained) > int(expect["memories_retained_max"]):
            fails.append(f"memories_retained={len(retained)} > {expect['memories_retained_max']}")

    for t in expect.get("retained_types_include") or []:
        types = [m.get("type") for m in retained if isinstance(m, dict)]
        if t not in types:
            fails.append(f"retained types {types} missing {t!r}")

    sid = trace.get("selected_dictation_id")
    if "selected_dictation_id" in expect and sid != expect["selected_dictation_id"]:
        fails.append(f"selected_dictation_id={sid!r} expected {expect['selected_dictation_id']!r}")
    if expect.get("selected_dictation_id_null") and sid:
        fails.append(f"expected no selected dictation, got {sid!r}")
    if "if_answer_must_select_from" in expect and decision == "answer":
        allowed = expect["if_answer_must_select_from"]
        if sid not in allowed:
            fails.append(f"selected {sid!r} not in {allowed}")

    for s in expect.get("reply_must_include") or []:
        if s not in reply:
            fails.append(f"reply missing {s!r}")
    for s in expect.get("reply_must_not_include") or []:
        if s in reply:
            fails.append(f"reply unexpectedly contains {s!r}")
    if expect.get("reply_must_include_any"):
        if not _contains_any(reply, expect["reply_must_include_any"]):
            fails.append(f"reply missing any of {expect['reply_must_include_any']}")

    considered_blob = " ".join(
        str(c.get("text", "")) if isinstance(c, dict) else str(c) for c in considered
    )
    combo = f"{reply}\n{considered_blob}"
    if expect.get("reply_or_considered_must_include_any"):
        if not _contains_any(combo, expect["reply_or_considered_must_include_any"]):
            fails.append(
                "reply/considered missing any of "
                f"{expect['reply_or_considered_must_include_any']}"
            )

    for phrase in expect.get("seed_memories_must_not_contain") or []:
        for text in seeded_memory_texts:
            low = text.lower()
            if "source_dictation_id=" in low:
                continue
            if "kivi_chat=true" in low or "source_interaction_id=" in low:
                continue
            if "kivi_memory" not in low and "source=seed" not in low:
                if not text.strip().startswith("["):
                    continue
            if phrase.lower() in low:
                fails.append(
                    f"seed memory contains forbidden paraphrase phrase {phrase!r}: {text[:80]!r}"
                )

    if expect.get("paraphrase_required"):
        if "hindsight_recall" not in tools:
            fails.append("paraphrase_required but hindsight_recall was not used")
        if not considered:
            fails.append("paraphrase_required but no memories_considered")

    return fails
