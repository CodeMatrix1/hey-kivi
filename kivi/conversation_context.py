"""Format recent conversation turns for LLM continuity (not stored or routed)."""

from __future__ import annotations

from typing import Any, Sequence


def format_continuity_block(
    context_messages: Sequence[dict[str, Any]] | None,
    current_message: str,
) -> str:
    """Build a deterministic prompt block from prior turns + current user message."""
    current = (current_message or "").strip()
    lines: list[str] = []

    if context_messages:
        lines.append("Recent conversation:")
        for msg in context_messages:
            role = str(msg.get("role") or "").strip().lower()
            content = str(msg.get("content") or "").strip()
            if role not in {"user", "assistant"} or not content:
                continue
            label = "User" if role == "user" else "Assistant"
            lines.append(f"{label}: {content}")
        lines.append("")

    lines.append("Current message:")
    lines.append(current)
    return "\n".join(lines)


def user_lines_from_continuity_block(continuity_context: str | None) -> list[str]:
    """Extract prior user utterances from a formatted continuity block."""
    if not continuity_context:
        return []
    lines: list[str] = []
    for raw in continuity_context.splitlines():
        stripped = raw.strip()
        if stripped.startswith("User:"):
            text = stripped.removeprefix("User:").strip()
            if text:
                lines.append(text)
    return lines
