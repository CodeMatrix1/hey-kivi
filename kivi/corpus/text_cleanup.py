"""Strip synthetic corpus-generation noise before retain or polish."""

from __future__ import annotations

import re

_PLANNING_NOTE = re.compile(
    r"\s*(?:I was |i was )?considering it around the \d+(?:st|nd|rd|th) planning note\.?",
    re.IGNORECASE,
)
_ACTIVITY_LOG = re.compile(
    r"\s*(?:,?\s*)?(?:This was |this was )?(?:part of )?(?:my )?"
    r"(?:activity log entry|recorded as activity log entry|documented in activity log entry)"
    r" \d+\.?",
    re.IGNORECASE,
)
_AS_DOCUMENTED = re.compile(
    r"\s*as documented in activity log entry \d+\.?",
    re.IGNORECASE,
)
_RECORDED_ENTRY = re.compile(
    r"\s*,?\s*which was recorded (?:as|in) activity log entry \d+\.?",
    re.IGNORECASE,
)
_THINKING_AHEAD = re.compile(
    r"^(?:I'm thinking ahead about this:\s*|For later,?\s*|A possible plan is that\s*)",
    re.IGNORECASE,
)


def strip_corpus_metadata_noise(text: str) -> str:
    """Remove planning-note / activity-log scaffolding from synthetic transcript text."""
    cleaned = (text or "").strip()
    if not cleaned:
        return cleaned
    cleaned = _THINKING_AHEAD.sub("", cleaned)
    cleaned = _PLANNING_NOTE.sub("", cleaned)
    cleaned = _ACTIVITY_LOG.sub("", cleaned)
    cleaned = _AS_DOCUMENTED.sub("", cleaned)
    cleaned = _RECORDED_ENTRY.sub("", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    if cleaned and cleaned[0].islower():
        cleaned = cleaned[0].upper() + cleaned[1:]
    return cleaned
