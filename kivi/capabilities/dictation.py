"""Dictation capability: find candidates and polish when confident."""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from hindsight_pipeline_2.kivi.capabilities.trace_utils import memory_card, record_llm
from hindsight_pipeline_2.kivi.config import DICTATION_SELECT_SYSTEM
from hindsight_pipeline_2.kivi.storage.dictation_store import DictationStore
from hindsight_pipeline_2.kivi.storage.lexical_store import LexicalStore
from hindsight_pipeline_2.kivi.llm import llm_json
from hindsight_pipeline_2.kivi.models import DecisionTrace
from hindsight_pipeline_2.kivi.tools import find_dictations, polish_dictation


_WEEKDAYS = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}
_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}
_ABSOLUTE_DATE = re.compile(
    r"\b(january|february|march|april|may|june|july|august|september|october|november|december)"
    r"\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})\b",
    re.IGNORECASE,
)
_STOPWORDS = {
    "a", "about", "all", "and", "any", "around", "at", "can", "did", "do", "exact",
    "fetch", "find", "for", "from", "get", "have", "i", "in", "it", "me", "message",
    "messages", "my", "note", "notes", "of", "on", "open", "original", "please", "polish",
    "rewrite", "said", "show", "slack", "tell", "that", "the", "this", "to", "verbatim",
    "what", "were", "words", "write", "written", "you", "dictation", "dictations", "meeting",
    # Natural-language find scaffolding (FTS requires every remaining token to appear in body).
    "where", "mentioned", "into", "concise", "update", "read", "give", "want", "need",
    "help", "make", "create", "draft", "short", "brief", "quick", "together", "already",
    "key", "points", "bring", "compile", "recap", "then", "also", "just", "only", "when",
    "while", "during", "into", "out", "up", "down", "use", "using", "used", "like",
    "plan", "travel", "weekend", "planning", "sharing", "friend", "friends",
    "with", "mentions", "place", "name", "preferences", "using",
}
_CLOCK_RE = re.compile(
    r"\b(?:around\s+)?(?:\d{1,2}:\d{2}\s*(?:a\.?m\.?|p\.?m\.?)?"
    r"|\d{1,2}\s*(?:a\.?m\.?|p\.?m\.?)|noon|midnight|morning|afternoon|evening)\b",
    re.IGNORECASE,
)
_MAX_POLISH_MATCHES = 5
_SINGLE_POLISH_RE = re.compile(
    r"\b(?:polish|rewrite|concise|brief|short|sharing|share|read in the meeting|"
    r"travel plan|for a friend|one note|single note)\b",
    re.IGNORECASE,
)


def wants_single_polished_note(message: str) -> bool:
    """True when the user expects one polished artifact, not a list of matches."""
    return bool(_SINGLE_POLISH_RE.search(message or ""))


def _utc_day(now: datetime | None) -> datetime:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    current = current.astimezone(timezone.utc)
    return current.replace(hour=0, minute=0, second=0, microsecond=0)


def _absolute_date_window(message: str) -> tuple[datetime | None, datetime | None, str]:
    """Parse explicit calendar dates such as ``August 20, 2026`` (UTC day window)."""
    match = _ABSOLUTE_DATE.search(message)
    if not match:
        return None, None, message
    month = _MONTHS[match.group(1).casefold()]
    day = int(match.group(2))
    year = int(match.group(3))
    start = datetime(year, month, day, tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    return start, end, _ABSOLUTE_DATE.sub(" ", message, count=1)


def _date_window(message: str, now: datetime) -> tuple[datetime | None, datetime | None, str]:
    """Extract one narrow calendar window and return text with it removed."""
    abs_start, abs_end, text = _absolute_date_window(message)
    if abs_start is not None:
        return abs_start, abs_end, text
    lower = message.casefold()
    patterns: list[tuple[re.Pattern[str], datetime, datetime]] = []
    next_match = re.search(r"\bnext\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", lower)
    if next_match:
        target = _WEEKDAYS[next_match.group(1)]
        delta = (target - now.weekday()) % 7 or 7
        start = now + timedelta(days=delta)
        patterns.append((re.compile(re.escape(next_match.group(0)), re.IGNORECASE), start, start + timedelta(days=1)))
    else:
        named = re.search(r"\b(today|yesterday|tomorrow|last week|next week)\b", lower)
        if named:
            phrase = named.group(1)
            if phrase == "today":
                start, end = now, now + timedelta(days=1)
            elif phrase == "yesterday":
                start, end = now - timedelta(days=1), now
            elif phrase == "tomorrow":
                start, end = now + timedelta(days=1), now + timedelta(days=2)
            else:
                week_start = now - timedelta(days=now.weekday())
                start = week_start + timedelta(days=-7 if phrase == "last week" else 7)
                end = start + timedelta(days=7)
            patterns.append((re.compile(re.escape(phrase), re.IGNORECASE), start, end))
        else:
            weekday = re.search(
                r"(?<!next )(?<!this )\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
                lower,
            )
            if weekday:
                target = _WEEKDAYS[weekday.group(1)]
                start = now - timedelta(days=(now.weekday() - target) % 7)
                patterns.append((re.compile(re.escape(weekday.group(1)), re.IGNORECASE), start, start + timedelta(days=1)))
    if not patterns:
        return None, None, message
    pattern, start, end = patterns[0]
    return start, end, pattern.sub(" ", message, count=1)


def find_params(message: str, *, now: datetime | None = None) -> dict[str, Any]:
    """Build deterministic FTS text and UTC calendar filters, without an LLM."""
    today = _utc_day(now)
    start, end, text = _date_window(message, today)
    text = _CLOCK_RE.sub(" ", text)
    tokens = re.findall(r"\w+", text.casefold(), flags=re.UNICODE)
    text_query = " ".join(token for token in tokens if token not in _STOPWORDS)
    return {
        "text_query": text_query,
        "date_start": start.isoformat() if start else None,
        "date_end": end.isoformat() if end else None,
        "occasion": "meeting" if re.search(r"\bmeeting\b", message, re.IGNORECASE) else None,
    }


def format_dictation_timestamp(value: str | None) -> str:
    """Turn a stored UTC ISO timestamp into a concise user-facing citation."""
    if not value:
        return "an unknown date"
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return value
        utc = parsed.astimezone(timezone.utc)
        return f"{utc.strftime('%A, %B')} {utc.day}, {utc.year} at {utc:%H:%M} UTC"
    except ValueError:
        # Existing data may have an invalid legacy timestamp; preserve it rather
        # than hiding the source reference or failing the dictation response.
        return value


def select_ambiguous_dictation(
    *,
    query: str,
    candidates: list[dict[str, Any]],
    selection_llm: Any | None,
    max_ids: int = 3,
) -> tuple[list[str], dict[str, Any]]:
    """Use an LLM only to resolve an otherwise ambiguous, bounded candidate set."""
    if selection_llm is None:
        return [], {"source": "skipped", "output": None}
    candidate_ids = {str(candidate["id"]) for candidate in candidates}
    payload = {
        "request": query,
        "candidates": [
            {
                "id": candidate["id"],
                "created_at": candidate["created_at"],
                "text": candidate["formatted_preview"],
            }
            # FTS ranks literal query echoes very highly. Give the selector a
            # deeper bounded pool so older declarative source notes are not
            # crowded out by later "find/show/what did I say" chat turns.
            for candidate in candidates[:24]
        ],
    }
    try:
        output = llm_json(selection_llm, DICTATION_SELECT_SYSTEM, json.dumps(payload))
    except Exception as exc:  # noqa: BLE001
        return [], {"source": "fallback", "output": {"error": str(exc)}}
    raw_ids = output.get("selected_ids")
    if not isinstance(raw_ids, list):
        raw_ids = []
    selected_ids: list[str] = []
    for raw_id in raw_ids:
        candidate_id = str(raw_id)
        if candidate_id in candidate_ids and candidate_id not in selected_ids:
            selected_ids.append(candidate_id)
        if len(selected_ids) >= max(1, max_ids):
            break
    return selected_ids, {"source": "llm", "output": output}


def _candidate_summary(candidate: dict[str, Any]) -> str:
    """Render a candidate without exposing internal storage IDs or raw ISO dates."""
    preview = str(candidate.get("formatted_preview") or "").strip()
    return f"- {format_dictation_timestamp(candidate.get('created_at'))} — {preview[:140]}…"


def _preview_key(candidate: dict[str, Any]) -> str:
    text = re.sub(r"\s+", " ", str(candidate.get("formatted_preview") or "").casefold()).strip()
    return text[:160]


def _fallback_selected_candidates(
    candidates: list[dict[str, Any]],
    *,
    max_notes: int = _MAX_POLISH_MATCHES,
) -> list[dict[str, Any]]:
    """Polish unique top-tier FTS hits when the selector cannot pick a single ID."""
    if not candidates:
        return []
    top_score = float(candidates[0]["score"])
    tier = [candidate for candidate in candidates if float(candidate["score"]) >= top_score - 1e-6]
    unique: list[dict[str, Any]] = []
    seen: set[str] = set()
    for candidate in tier:
        key = _preview_key(candidate)
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
        if len(unique) >= max_notes:
            break
    if max_notes == 1 and unique:
        return [_most_recent_candidate(unique)]
    return unique


def _most_recent_candidate(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    """Pick the newest dictation when several near-duplicate FTS hits tie."""
    return max(candidates, key=lambda c: str(c.get("created_at") or ""))


def _prefer_content_dictations(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Rank preference-teaching rows after real notes when both match the same query."""
    content = [candidate for candidate in candidates if not str(candidate.get("id", "")).startswith("lexical_")]
    teaching = [candidate for candidate in candidates if str(candidate.get("id", "")).startswith("lexical_")]
    if content:
        return content + teaching
    return candidates


def run_dictation(
    *,
    store: DictationStore,
    lexical_store: LexicalStore,
    memory: Any,
    user_id: str,
    canonical: str,
    raw: str | None = None,
    text_llm: Any,
    selection_llm: Any | None = None,
    trace: DecisionTrace,
) -> list[str]:
    """Find and polish one clear match, LLM-vetted notes, or all top-tier ties."""
    parts: list[str] = []
    single_polish = wants_single_polished_note(canonical)
    max_select = 1 if single_polish else 3
    max_fallback = 1 if single_polish else _MAX_POLISH_MATCHES
    # FTS must use the user's original wording; lexical canonicalization would
    # replace search aliases (e.g. Trivandrum) before we can match stored notes.
    params = find_params(raw or canonical)
    candidates = _prefer_content_dictations(
        find_dictations(
            store,
            user_id,
            text_query=str(params["text_query"]),
            date_start=params["date_start"],
            date_end=params["date_end"],
            limit=24,
        )
    )
    # Never treat this turn's own chat dictation as a find hit.
    if trace.source_dictation_id:
        candidates = [c for c in candidates if c.get("id") != trace.source_dictation_id]
    trace.tools_used.append("find_dictations")
    trace.find_query = params
    trace.candidates = candidates

    if not candidates:
        trace.decision = "abstain"
        trace.reason = "No matching dictations."
        parts.append("I couldn't find a dictation matching that. Try another date or search terms.")
        return parts

    top = candidates[0]
    second = candidates[1] if len(candidates) > 1 else None
    high_conf = top["score"] >= 0.55 and (
        second is None or (top["score"] - second["score"]) >= 0.12
    )
    if not high_conf:
        selected_ids, select_meta = select_ambiguous_dictation(
            query=canonical,
            candidates=candidates,
            selection_llm=selection_llm,
            max_ids=max_select,
        )
        record_llm(
            trace,
            "select_dictation_candidate",
            source=str(select_meta["source"]),
            output=select_meta["output"],
        )
        trace.tools_used.append("select_dictation_candidate")
        if selected_ids:
            selected_candidates = [
                next(candidate for candidate in candidates if candidate["id"] == selected_id)
                for selected_id in selected_ids[:max_select]
            ]
        else:
            selected_candidates = _fallback_selected_candidates(
                candidates, max_notes=max_fallback
            )
            if not selected_candidates:
                trace.decision = "abstain"
                trace.reason = "No matching dictations after candidate filtering."
                parts.append("I couldn't find a dictation matching that. Try another date or search terms.")
                return parts
    else:
        selected_candidates = [top]

    occasion = params.get("occasion") or "general cleanup"
    polished_notes: list[dict[str, Any]] = []
    seen = {m.get("id") for m in trace.memories_considered}
    for candidate in selected_candidates:
        polish = polish_dictation(
            store,
            memory,
            user_id,
            candidate["id"],
            occasion,
            text_llm=text_llm,
            lexical_store=lexical_store,
        )
        if not polish.get("ok"):
            continue
        polished_notes.append(polish)
        record_llm(
            trace,
            "polish",
            source=str(polish.get("llm_source") or "skipped"),
            output=polish.get("llm_output"),
        )
        if polish.get("retrieval_backend"):
            if trace.retrieval_backend == "none":
                rb = polish["retrieval_backend"]
                trace.retrieval_backend = "hindsight" if rb in {"hindsight", "stub"} else "none"
            if not trace.retrieval_query:
                trace.retrieval_query = polish.get("retrieval_query")
        for recalled in polish.get("retrieved") or []:
            card = memory_card(recalled, store=store, user_id=user_id)
            if card.get("id") not in seen:
                trace.memories_considered.append(card)
                seen.add(card.get("id"))
        for pref in polish.get("applied_preferences") or []:
            if pref not in trace.applied_preferences:
                trace.applied_preferences.append(pref)
    trace.tools_used.append("polish_dictation")
    if not polished_notes:
        trace.decision = "abstain"
        trace.reason = "Selected dictation could not be polished."
        parts.append("I found relevant notes but couldn't prepare them.")
        return parts
    trace.selected_dictation_ids = [str(note["dictation_id"]) for note in polished_notes]
    trace.selected_dictation_id = trace.selected_dictation_ids[0]
    trace.decision = "answer"
    if len(polished_notes) == 1:
        trace.reason = "Selected and polished one relevant dictation."
    else:
        trace.reason = (
            f"Polished {len(polished_notes)} relevant dictation(s) "
            f"(multiple top-tier matches; no single winner required)."
        )
    if len(polished_notes) == 1:
        note = polished_notes[0]
        parts.append(
            f"I used your note from {format_dictation_timestamp(note.get('created_at'))}.\n\n"
            f"{note['polished_text']}"
        )
    else:
        notes = []
        for note in polished_notes:
            notes.append(
                f"### {format_dictation_timestamp(note.get('created_at'))}\n\n"
                f"{note['polished_text']}"
            )
        parts.append("I used these relevant notes:\n\n" + "\n\n".join(notes))
    return parts
