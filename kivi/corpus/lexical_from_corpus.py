"""Deterministic lexical mapping extraction from corpus preference rows."""

from __future__ import annotations

import re

from hindsight_pipeline_2.kivi.models import DictationRecord, LexicalMapping

_INSTEAD_OF = re.compile(
    r"(?:please\s+)?(?:use|write|say)\s+(.+?)\s+instead of\s+(.+?)\.?$",
    re.IGNORECASE,
)
_RATHER_THAN = re.compile(
    r"please call it\s+(.+?)\s+rather than\s+(.+?)\.?$",
    re.IGNORECASE,
)
_PREFER_TERM = re.compile(
    r"i prefer (?:saying|the term)\s+(.+?)\s+(?:instead of|over)\s+(.+?)\.?$",
    re.IGNORECASE,
)
_NAME_AS = re.compile(
    r"please always write my name as\s+(.+?)\.?$",
    re.IGNORECASE,
)


def mapping_from_formatted(text: str, *, kind: str = "terminology") -> LexicalMapping | None:
    """Parse one preference sentence into alias→canonical when pattern matches."""
    body = (text or "").strip()
    if not body:
        return None
    for pattern in (_INSTEAD_OF, _RATHER_THAN, _PREFER_TERM):
        match = pattern.search(body)
        if match:
            canonical = match.group(1).strip()
            alias = match.group(2).strip()
            if canonical and alias and canonical.casefold() != alias.casefold():
                return LexicalMapping(alias=alias, canonical=canonical, kind=kind)
    return None


def mapping_from_corpus_record(record: DictationRecord) -> LexicalMapping | None:
    """Extract a lexical mapping from a corpus row when applicable."""
    if not record.id.startswith("lexical_"):
        return None
    kind = "name" if "name" in record.formatted.casefold() else "terminology"
    return mapping_from_formatted(record.formatted, kind=kind)
