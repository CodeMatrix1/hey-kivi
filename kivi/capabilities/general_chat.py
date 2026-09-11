"""General chat: normal LLM reply when no retrieval flags are set."""

from __future__ import annotations

from typing import Any

from hindsight_pipeline_2.kivi.capabilities.trace_utils import record_llm
from hindsight_pipeline_2.kivi.config import GENERAL_CHAT_FALLBACK, GENERAL_CHAT_SYSTEM
from hindsight_pipeline_2.kivi.models import DecisionTrace


def run_general_chat(
    *,
    message: str,
    text_llm: Any,
    trace: DecisionTrace,
    lexical_notes: list[str] | None = None,
) -> list[str]:
    """Reply for turns with wants_dictation=false and wants_cross_recall=false."""
    notes = "\n".join(lexical_notes or [])
    user = message
    if notes:
        user = (
            f"User message:\n{message}\n\n"
            f"(Already confirmed to the user this turn:\n{notes}\n"
            "Keep your reply complementary; do not repeat that confirmation verbatim.)"
        )

    if text_llm is None:
        record_llm(
            trace,
            "general_chat",
            source="fallback",
            output=GENERAL_CHAT_FALLBACK,
        )
        trace.decision = "answer"
        if not trace.reason:
            trace.reason = "General chat; no LLM — fallback."
        return [GENERAL_CHAT_FALLBACK]

    try:
        text = text_llm(GENERAL_CHAT_SYSTEM, user).strip() or GENERAL_CHAT_FALLBACK
        record_llm(trace, "general_chat", source="llm", output=text)
        trace.decision = "answer"
        if not trace.reason:
            trace.reason = "General chat (no retrieval flags)."
        return [text]
    except Exception as exc:  # noqa: BLE001
        record_llm(
            trace,
            "general_chat",
            source="fallback",
            output={"error": str(exc), "reply": GENERAL_CHAT_FALLBACK},
        )
        trace.decision = "answer"
        if not trace.reason:
            trace.reason = f"General chat LLM failed: {exc}"
        return [GENERAL_CHAT_FALLBACK]
