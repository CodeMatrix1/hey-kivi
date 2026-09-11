"""Narrow LLM lexical extractor + deterministic validation (no store / Hindsight)."""

from __future__ import annotations

import json
import re
from typing import Any, Callable

from hindsight_pipeline_2.kivi.config import LEXICAL_EXTRACT_SYSTEM
from hindsight_pipeline_2.kivi.llm import llm_json
from hindsight_pipeline_2.kivi.models import LexicalExtraction, LexicalMapping

GenerateFn = Callable[[str, str], str]

_NAME_CUES = re.compile(
    r"\b(my name|spell my name|name is|i am called|call me)\b",
    re.I,
)


def extract_lexical_mappings(
    message: str,
    *,
    llm: GenerateFn | None = None,
    meta: dict[str, Any] | None = None,
) -> LexicalExtraction:
    """Propose mappings from the current message only (no store / Hindsight).

    If ``meta`` is provided, it is filled with ``source`` and ``output`` for tracing.
    """
    text = (message or "").strip()
    if not text:
        if meta is not None:
            meta.update({"source": "skipped", "output": None})
        return LexicalExtraction()
    if llm is None:
        if meta is not None:
            meta.update({"source": "skipped", "output": None})
        return LexicalExtraction()
    try:
        raw = llm_json(llm, LEXICAL_EXTRACT_SYSTEM, text)
    except Exception as exc:  # noqa: BLE001
        if meta is not None:
            meta.update({"source": "fallback", "output": {"error": str(exc)}})
        return LexicalExtraction()
    if meta is not None:
        meta.update({"source": "llm", "output": raw})
    return _parse_extraction(raw)


def _parse_extraction(raw: dict[str, Any]) -> LexicalExtraction:
    items = raw.get("mappings") if isinstance(raw, dict) else None
    if not isinstance(items, list):
        return LexicalExtraction()
    out: list[LexicalMapping] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        alias = str(item.get("alias") or "").strip()
        canonical = str(item.get("canonical") or "").strip()
        kind = str(item.get("kind") or "alias").strip().lower()
        if kind not in {"name", "spelling", "alias", "terminology"}:
            kind = "alias"
        if not alias or not canonical:
            continue
        out.append(LexicalMapping(alias=alias, canonical=canonical, kind=kind))  # type: ignore[arg-type]
    return LexicalExtraction(mappings=out)


def validate_lexical_extraction(
    message: str,
    extraction: LexicalExtraction,
) -> LexicalExtraction:
    """Deterministic gate: both strings must appear exactly; name kind needs name cues."""
    text = message or ""
    kept: list[LexicalMapping] = []
    for m in extraction.mappings:
        alias = m.alias.strip()
        canonical = m.canonical.strip()
        if not alias or not canonical:
            continue
        if alias == canonical:
            continue
        if alias not in text or canonical not in text:
            continue
        kind = m.kind
        if kind == "name" and not _NAME_CUES.search(text):
            # Downgrade mis-tagged name mappings rather than inventing
            kind = "alias"
        kept.append(LexicalMapping(alias=alias, canonical=canonical, kind=kind))
    return LexicalExtraction(mappings=kept)


def scripted_lexical_llm(payload: dict[str, Any]) -> GenerateFn:
    """Test helper: always returns the given JSON payload."""

    def _gen(_system: str, _user: str) -> str:
        return json.dumps(payload)

    return _gen
