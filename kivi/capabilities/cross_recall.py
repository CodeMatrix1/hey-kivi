"""Cross-recall: Hindsight recall + answer synthesis."""

from __future__ import annotations

import re
from typing import Any

from hindsight_pipeline_2.kivi.capabilities.trace_utils import memory_card, record_llm
from hindsight_pipeline_2.kivi.corpus.text_cleanup import strip_corpus_metadata_noise
from hindsight_pipeline_2.kivi.config import SYNTHESIZE_SYSTEM
from hindsight_pipeline_2.kivi.models import DecisionTrace
from hindsight_pipeline_2.kivi.query_tokens import substantive_query_tokens


_SYNTHESIS_ABSTAIN_PATTERNS = (
    r"^i (?:don't|do not) know\b",
    r"^i (?:don't|do not) have (?:enough|any)\b",
    r"^(?:sorry,?\s+)?i (?:can't|cannot) (?:say|answer|find|tell)\b",
    r"^(?:sorry,?\s+)?(?:i'm|i am) not (?:sure|able)\b",
    r"^there(?:'s| is) no (?:information|record|mention)\b",
    r"not (?:in|from) (?:your )?history",
    r"no (?:useful|relevant) information",
)


def is_synthesis_abstention(text: str) -> bool:
    """True when the synthesizer explicitly declines to answer from memories."""
    normalized = re.sub(r"\s+", " ", (text or "").strip().casefold())
    if not normalized:
        return True
    return any(re.search(pattern, normalized) for pattern in _SYNTHESIS_ABSTAIN_PATTERNS)


def is_terse_abstention(text: str) -> bool:
    """True for bare declines (e.g. ``I don't know.``) without added explanation."""
    normalized = re.sub(r"\s+", " ", (text or "").strip())
    if not normalized:
        return True
    if len(normalized) < 72:
        return True
    if re.search(r"\b(?:but|however|though)\b", normalized, re.IGNORECASE):
        return False
    if normalized.count(".") >= 2 or normalized.count(";") >= 1:
        return False
    return True


def _memory_body(text: str) -> str:
    """Strip ingest/chat provenance header if present."""
    t = (text or "").strip()
    if t.startswith("[source_dictation_id="):
        parts = t.split("\n", 1)
        body = parts[1].strip() if len(parts) > 1 else ""
        return strip_corpus_metadata_noise(body)
    if t.startswith("[KIVI_MEMORY"):
        parts = t.split("\n", 1)
        body = parts[1].strip() if len(parts) > 1 else t
        return strip_corpus_metadata_noise(body)
    return strip_corpus_metadata_noise(t)


def _token_in_text(token: str, text: str) -> bool:
    if re.search(rf"\b{re.escape(token)}\b", text):
        return True
    root = re.sub(r"(ing|ed|es|s)$", "", token)
    return len(root) >= 5 and root in text


def _memories_support_query(query: str, recalled: list[dict[str, Any]]) -> bool:
    """True when recalled memories plausibly support answering this question."""
    if not recalled:
        return False
    tokens = substantive_query_tokens(query)
    if not tokens:
        # Only scaffolding left (e.g. "what have I been working on lately?") — trust recall.
        return True
    matched: set[str] = set()
    for item in recalled:
        body = _memory_body(str(item.get("text") or "")).casefold()
        for token in tokens:
            if _token_in_text(token, body):
                matched.add(token)
    return bool(matched)


def _bullet_fallback_answer(recalled: list[dict[str, Any]]) -> str:
    """Deterministic summary when the LLM declines but recall is on-topic."""
    seen: set[str] = set()
    lines: list[str] = []
    for item in recalled[:8]:
        body = _memory_body(str(item.get("text") or "")).strip()
        if not body:
            continue
        key = re.sub(r"\s+", " ", body.casefold())
        if key in seen:
            continue
        seen.add(key)
        lines.append(f"- {body[:300]}")
    if not lines:
        return "I don't have enough in your history to answer that from what I know."
    return "Based on what you've said before:\n\n" + "\n".join(lines[:5])


def synthesize_answer(
    query: str,
    recalled: list[dict[str, Any]],
    text_llm: Any,
) -> tuple[str, dict[str, Any]]:
    """Build a user-facing answer from recalled memories."""
    cards = [memory_card(r) for r in recalled[:6]]
    bullets = "\n".join(
        f"- [{c.get('type') or 'Memory'}] {c.get('text', '')[:400]}" for c in cards
    )
    if text_llm is not None:
        user = f"Question: {query}\n\nMemories:\n{bullets}"
        try:
            text = text_llm(SYNTHESIZE_SYSTEM, user).strip()
            return text, {"source": "llm", "output": text}
        except Exception as exc:  # noqa: BLE001
            fallback = "Here's what I found in your memories related to that:\n" + bullets
            return fallback, {
                "source": "fallback",
                "output": {"error": str(exc), "bullets": bullets},
            }
    fallback = "Here's what I found in your memories related to that:\n" + bullets
    return fallback, {"source": "fallback", "output": fallback}


def run_cross_recall(
    *,
    memory: Any,
    user_id: str,
    raw: str,
    canonical: str,
    text_llm: Any,
    selection_llm: Any = None,
    store: Any | None = None,
    trace: DecisionTrace,
) -> list[str]:
    """Recall prior semantic memories and append a synthesized reply part."""
    parts: list[str] = []
    query = canonical
    recall_limit = 32 if getattr(memory, "backend_name", None) == "stub" else 12
    echo_bodies = {canonical.strip(), query.strip(), raw.strip()}
    current_dictation = trace.source_dictation_id

    def _filter_recalled(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        kept: list[dict[str, Any]] = []
        for r in candidates:
            meta = r.get("metadata") or {}
            if current_dictation and (
                meta.get("dictation_id") == current_dictation
                or str(r.get("id") or "") == f"dict_{current_dictation}"
            ):
                continue
            raw_text = str(r.get("text") or "")
            body = _memory_body(raw_text)
            if body in echo_bodies:
                continue
            if body.startswith(query.strip()[:40]) if query.strip() else False:
                continue
            if current_dictation and f"source_dictation_id={current_dictation}" in raw_text:
                continue
            kept.append(r)
        return kept

    recalled = _filter_recalled(memory.recall(user_id, query, limit=recall_limit))
    if not recalled and getattr(memory, "backend_name", None) == "stub":
        recalled = _filter_recalled(memory.recall(user_id, "", limit=recall_limit))
    backend = getattr(memory, "backend_name", "none")
    trace.retrieval_backend = "hindsight" if backend in {"hindsight", "stub"} else "none"
    trace.retrieval_query = query
    trace.tools_used.append("hindsight_recall")
    trace.memories_considered = [
        memory_card(r, store=store, user_id=user_id) for r in recalled
    ]
    if not recalled:
        trace.decision = "abstain"
        trace.reason = "No relevant durable memories for cross-recall."
        parts.append(
            "I don't have enough in your history to say what you've been working on for that."
        )
        return parts

    memories_support = _memories_support_query(query, recalled)
    if not memories_support:
        trace.decision = "abstain"
        trace.reason = (
            f"Recalled {len(recalled)} memories but none support an answer to this question."
        )
        parts.append("I don't have enough in your history to answer that from what I know.")
        return parts

    synth, synth_meta = synthesize_answer(query, recalled, text_llm)
    record_llm(
        trace,
        "synthesize",
        source=str(synth_meta.get("source") or "fallback"),
        output=synth_meta.get("output") or synth,
    )
    if is_synthesis_abstention(synth):
        if memories_support and is_terse_abstention(synth):
            # LLM gave a bare "I don't know" despite on-topic recall — surface memories.
            synth = _bullet_fallback_answer(recalled)
            trace.decision = "answer"
            trace.reason = (
                f"Cross-recall: LLM declined; summarized {len(recalled)} on-topic memories."
            )
        else:
            trace.decision = "abstain"
            if is_terse_abstention(synth):
                trace.reason = (
                    f"Recalled {len(recalled)} memories but none support an answer "
                    "to this question."
                )
                synth = "I don't have enough in your history to answer that from what I know."
            else:
                trace.reason = (
                    "Cross-recall: LLM abstained with explanation from recalled context."
                )
    else:
        trace.decision = "answer"
        trace.reason = (
            f"Cross-recall: synthesized from {len(recalled)} Hindsight memories "
            f"(Fact/Preference/Episode when typed)."
        )
    parts.append(synth)
    return parts
