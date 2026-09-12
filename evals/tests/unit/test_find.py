"""Unit tests — dictation find (FTS5) and deterministic query parsing.

Tier: unit (offline stub, no full agent required)

Tests:
- test_find_params_strips_stopwords_dates_and_clock_noise — find_params splits FTS terms, UTC date window, and polish occasion from a Slack/5pm query
- test_find_params_absolute_date_and_clock — explicit dates (August 20, 2026) plus clock stripping for time-based find
- test_find_params_payments_review_strips_query_scaffolding — strips "where mentioned" scaffolding so FTS gets "payments team review"
- test_payments_review_dictation_is_findable — corpus-style payments-review query returns the matching dictation id
- test_ambiguous_tied_matches_polish_all_unique_top_tier — multiple top-tier FTS ties polish all rather than abstaining when selection is skipped
- test_clock_is_not_a_date_filter_and_is_removed_from_text — "17:00" is not treated as a calendar date filter
- test_dictation_timestamp_is_human_friendly_and_preserves_bad_legacy_values — readable UTC timestamps; bad legacy strings pass through
- test_calendar_windows_are_utc_and_exclusive — today/yesterday/last week/Friday/next Friday → correct UTC half-open windows (parametrized)
- test_sanitize_fts_query_removes_operators_and_syntax — user input cannot inject FTS MATCH operators
- test_fts_ranks_phrase_over_distractor_and_syncs_insert — phrase match outranks partial distractor; INSERT trigger indexes new rows
- test_combined_text_date_and_user_isolation — text + date window returns only the matching user’s dictation
- test_explicit_miss_never_falls_back_to_recency — no FTS hit returns empty, not unrelated recent notes
- test_recency_date_validation_and_deterministic_ties — date-only search, invalid ranges, limit=0, stable tie ordering
- test_fts_migration_backfills_existing_dictations — legacy DB without FTS gets backfilled on store init
- test_clear_user_clears_source_and_fts_index — clear_user removes dictations and their FTS entries
- test_fts_has_insert_trigger_only — exactly one FTS trigger (INSERT only; dictations are immutable)
- test_dictation_trace_keeps_occasion_out_of_find — occasion appears in trace but not in FTS find_query params
- test_llm_selection_ignores_prior_question_and_uses_source_note — LLM selector picks source note over question echo
- test_llm_selection_returns_multiple_reasonable_source_notes — selector may return multiple substantive notes, excluding echoes
- test_llm_selector_receives_deeper_candidate_pool_than_display_limit — selection pool is deeper than UI display cap
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from hindsight_pipeline_2.kivi.capabilities.dictation import (
    find_params,
    format_dictation_timestamp,
    run_dictation,
    select_ambiguous_dictation,
)
from hindsight_pipeline_2.kivi.storage.dictation_store import DictationStore, sanitize_fts_query
from hindsight_pipeline_2.kivi.storage.lexical_store import LexicalStore
from hindsight_pipeline_2.kivi.models import DecisionTrace, DictationRecord, LexicalMapping


NOW = datetime(2026, 9, 4, 15, 30, tzinfo=timezone.utc)  # Friday


def add(store: DictationStore, ident: str, text: str, created_at: str, user: str = "u") -> None:
    store.add_dictation(DictationRecord(
        id=ident, user_id=user, asr=text.lower(), formatted=text, created_at=created_at
    ))


def test_find_params_strips_stopwords_dates_and_clock_noise():
    """Parser separates searchable terms, date windows, and polish occasion."""
    params = find_params(
        "Find my Slack dictation about API rate limits from yesterday around 5pm for the meeting.",
        now=NOW,
    )
    assert params == {
        "text_query": "api rate limits",
        "date_start": "2026-09-03T00:00:00+00:00",
        "date_end": "2026-09-04T00:00:00+00:00",
        "occasion": "meeting",
    }


def test_find_params_absolute_date_and_clock():
    """Explicit calendar dates (e.g. August 20, 2026) narrow the UTC day window."""
    params = find_params(
        "Find my dictation from August 20, 2026 around 8:10 PM about Thiruvananthapuram and polish it.",
        now=NOW,
    )
    assert params["date_start"] == "2026-08-20T00:00:00+00:00"
    assert params["date_end"] == "2026-08-21T00:00:00+00:00"
    assert params["text_query"] == "thiruvananthapuram"


def test_find_params_payments_review_strips_query_scaffolding():
    """Scaffolding words like 'where mentioned' must not reach FTS (AND semantics)."""
    params = find_params(
        "Find the dictation where I mentioned the payments team review and polish it "
        "into a concise update I can read in the meeting.",
        now=NOW,
    )
    assert params["text_query"] == "payments team review"
    assert params["occasion"] == "meeting"


def test_payments_review_dictation_is_findable(store: DictationStore):
    """Payments-review corpus phrasing matches after stopword stripping."""
    add(
        store,
        "pay_review",
        "I had a project review with the payments team yesterday.",
        "2026-09-04T10:00:00+00:00",
    )
    params = find_params(
        "Find the dictation where I mentioned the payments team review and polish it "
        "into a concise update I can read in the meeting.",
        now=NOW,
    )
    hits = store.find("u", text_query=params["text_query"])
    assert [hit["id"] for hit in hits] == ["pay_review"]


def test_ambiguous_tied_matches_polish_one_note_for_concise_request(
    store: DictationStore, tmp_path: Path
):
    """Concise polish requests return one note (most recent top-tier tie), not a dump."""
    body = "I had a project review with the payments team yesterday."
    add(store, "a", body, "2026-08-12T07:10:00+00:00")
    add(store, "b", body, "2026-08-08T12:30:00+00:00")
    add(store, "c", "Earlier, i had a project review with the payments team yesterday.", "2026-08-12T18:54:00+00:00")
    trace = DecisionTrace()
    result = run_dictation(
        store=store,
        lexical_store=LexicalStore(tmp_path / "find.sqlite3"),
        memory=None,
        user_id="u",
        canonical=(
            "Find the dictation where I mentioned the payments team review and polish it "
            "into a concise update I can read in the meeting."
        ),
        text_llm=None,
        selection_llm=None,
        trace=trace,
    )
    assert trace.decision == "answer"
    assert "I used your note from" in result[0]
    assert "###" not in result[0]
    assert trace.reason == "Selected and polished one relevant dictation."


def test_clock_is_not_a_date_filter_and_is_removed_from_text():
    """Clock references are ignored for retrieval rather than treated as dates."""
    params = find_params("Find my note about internship at 17:00", now=NOW)
    assert params["text_query"] == "internship"
    assert params["date_start"] is None
    assert params["date_end"] is None


def test_dictation_timestamp_is_human_friendly_and_preserves_bad_legacy_values():
    """User citations are readable while malformed legacy timestamps remain visible."""
    assert format_dictation_timestamp("2026-09-07T11:58:32+00:00") == "Monday, September 7, 2026 at 11:58 UTC"
    assert format_dictation_timestamp("not-a-date") == "not-a-date"


@pytest.mark.parametrize(
    ("phrase", "start", "end"),
    [
        ("today", "2026-09-04", "2026-09-05"),
        ("yesterday", "2026-09-03", "2026-09-04"),
        ("last week", "2026-08-24", "2026-08-31"),
        ("friday", "2026-09-04", "2026-09-05"),
        ("next friday", "2026-09-11", "2026-09-12"),
    ],
)
def test_calendar_windows_are_utc_and_exclusive(phrase: str, start: str, end: str):
    """Supported calendar phrases map to reproducible UTC half-open windows."""
    params = find_params(f"find notes {phrase}", now=NOW)
    assert params["date_start"].startswith(start)
    assert params["date_end"].startswith(end)


def test_sanitize_fts_query_removes_operators_and_syntax():
    """User input becomes literal FTS terms, never executable MATCH syntax."""
    assert sanitize_fts_query('payment OR refund') == '"payment" "refund"'
    assert sanitize_fts_query('"payment reconciliation"') == '"payment" "reconciliation"'
    assert sanitize_fts_query('payment* NEAR(refund) body:secret') == '"payment" "refund" "secret"'
    assert sanitize_fts_query("OR NOT NEAR") == ""


def test_fts_ranks_phrase_over_distractor_and_syncs_insert(store: DictationStore):
    """The INSERT trigger indexes new rows and FTS rejects missing query terms."""
    add(store, "exact", "Payment reconciliation launch plan.", "2026-09-04T10:00:00+00:00")
    add(store, "distractor", "Payment plan for the launch.", "2026-09-05T10:00:00+00:00")
    hits = store.find("u", text_query="payment reconciliation")
    assert [hit["id"] for hit in hits] == ["exact"]
    assert hits[0]["evidence"] == ["fts"]
    assert hits[0]["score"] == 0.75


def test_combined_text_date_and_user_isolation(store: DictationStore):
    """Text/date search returns only matching records for the requested user."""
    add(store, "before", "Internship update.", "2026-09-03T23:59:59+00:00")
    add(store, "inside", "Internship update.", "2026-09-04T12:00:00+00:00")
    add(store, "other", "Internship update.", "2026-09-04T12:01:00+00:00", user="other")
    hits = store.find(
        "u", text_query="internship", date_start="2026-09-04T00:00:00+00:00",
        date_end="2026-09-05T00:00:00+00:00",
    )
    assert [hit["id"] for hit in hits] == ["inside"]
    assert hits[0]["evidence"] == ["fts", "date_window"]
    assert hits[0]["score"] == 1.0


def test_explicit_miss_never_falls_back_to_recency(store: DictationStore):
    """An explicit text miss returns no candidates instead of unrelated recency hits."""
    add(store, "recent", "Recent note.", "2026-09-04T12:00:00+00:00")
    assert store.find("u", text_query="absent phrase") == []


def test_recency_date_validation_and_deterministic_ties(store: DictationStore):
    """Fallback, date-only, invalid-input, and tie ordering contracts are stable."""
    for ident in ("a", "b", "c", "d"):
        add(store, ident, "Same body.", "2026-09-04T12:00:00+00:00")
    assert [r["id"] for r in store.find("u")] == ["d", "c", "b"]
    date_only = store.find(
        "u", date_start="2026-09-04T00:00:00+00:00", date_end="2026-09-05T00:00:00+00:00"
    )
    assert date_only[0]["score"] == 0.35 and date_only[0]["evidence"] == ["date_window"]
    assert store.find("u", date_start="2026-09-05", date_end="2026-09-04") == []
    assert store.find("u", limit=0) == []


def test_fts_migration_backfills_existing_dictations(tmp_path: Path):
    """Creating FTS on a legacy database indexes its pre-existing dictations once."""
    db = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(db) as conn:
        conn.execute(
            "CREATE TABLE dictations (id TEXT PRIMARY KEY, user_id TEXT NOT NULL, asr TEXT NOT NULL, formatted TEXT NOT NULL, created_at TEXT NOT NULL, extra_json TEXT DEFAULT '{}')"
        )
        conn.execute(
            "INSERT INTO dictations VALUES ('legacy', 'u', 'old transcript', 'Legacy migration note.', '2026-09-04T10:00:00+00:00', '{}')"
        )
    store = DictationStore(db)
    assert [r["id"] for r in store.find("u", text_query="migration")] == ["legacy"]


def test_legacy_global_id_pk_migrates_to_composite_pk(tmp_path: Path):
    """Legacy dictations with a global id PK are migrated to (user_id, id)."""
    db = tmp_path / "legacy_pk.sqlite3"
    with sqlite3.connect(db) as conn:
        conn.execute(
            "CREATE TABLE dictations (id TEXT PRIMARY KEY, user_id TEXT NOT NULL, asr TEXT NOT NULL, formatted TEXT NOT NULL, created_at TEXT NOT NULL, extra_json TEXT DEFAULT '{}')"
        )
        conn.execute(
            "INSERT INTO dictations VALUES ('shared', 'user_a', 'alpha', 'Alpha note.', '2026-09-04T10:00:00+00:00', '{}')"
        )
    store = DictationStore(db)
    store.add_dictation(
        DictationRecord(
            id="shared",
            user_id="user_b",
            asr="beta",
            formatted="Beta note.",
            created_at="2026-09-04T11:00:00+00:00",
        )
    )
    assert store.get("user_a", "shared") is not None
    assert store.get("user_b", "shared") is not None
    assert [r["id"] for r in store.find("user_a", text_query="alpha")] == ["shared"]
    assert [r["id"] for r in store.find("user_b", text_query="beta")] == ["shared"]


def test_clear_user_clears_source_and_fts_index(store: DictationStore):
    """A user reset removes both source rows and their searchable FTS entries."""
    add(store, "gone", "Delete this indexed record.", "2026-09-04T10:00:00+00:00")
    store.clear_user("u")
    assert store.find("u", text_query="indexed") == []
    add(store, "gone", "Replacement after reset.", "2026-09-04T11:00:00+00:00")
    assert [r["id"] for r in store.find("u", text_query="replacement")] == ["gone"]


def test_fts_has_insert_trigger_only(store: DictationStore):
    """Immutable dictations use exactly one FTS synchronization trigger: INSERT."""
    with sqlite3.connect(store.db_path) as conn:
        triggers = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='trigger'")]
    assert triggers == ["dictations_fts_insert"]


def test_dictation_trace_keeps_occasion_out_of_find(store: DictationStore, tmp_path: Path):
    """The trace audits occasion, but only text/date parameters reach retrieval."""
    add(store, "rate", "API rate limits before launch.", "2026-09-04T10:00:00+00:00")
    trace = DecisionTrace()
    result = run_dictation(
        store=store,
        lexical_store=LexicalStore(tmp_path / "find.sqlite3"),
        memory=None,
        user_id="u",
        canonical="Find my Slack dictation about API rate limits for the meeting.",
        text_llm=None,
        trace=trace,
    )
    assert trace.find_query == {
        "text_query": "api rate limits",
        "date_start": None,
        "date_end": None,
        "occasion": "meeting",
    }
    assert trace.selected_dictation_id == "rate"
    assert result


def test_llm_selection_ignores_prior_question_and_uses_source_note(
    store: DictationStore, tmp_path: Path
):
    """Ambiguous matches use LLM selection to reject question echoes before polish."""
    add(
        store,
        "prior_question",
        "What is my favourite quote?",
        "2026-09-07T12:00:43+00:00",
    )
    add(
        store,
        "source_quote",
        'My favourite quote is: "Life comes from you and not at you and that takes time."',
        "2026-09-07T11:58:32+00:00",
    )
    trace = DecisionTrace()

    def select_quote(_system: str, _prompt: str) -> str:
        return '{"selected_ids":["source_quote"],"reason":"The other candidate is only a question."}'

    result = run_dictation(
        store=store,
        lexical_store=LexicalStore(tmp_path / "find.sqlite3"),
        memory=None,
        user_id="u",
        canonical="Show me my favourite quote.",
        text_llm=None,
        selection_llm=select_quote,
        trace=trace,
    )
    assert trace.decision == "answer"
    assert trace.selected_dictation_id == "source_quote"
    assert "select_dictation_candidate" in trace.tools_used
    assert "Life comes from you" in result[0]


def test_llm_selection_returns_multiple_reasonable_source_notes(
    store: DictationStore, tmp_path: Path
):
    """Selector may return several substantive notes while excluding a query echo."""
    add(store, "question", "What did I say about the internship?", "2026-09-07T12:02:00+00:00")
    add(store, "offer", "The internship offer starts in June.", "2026-09-06T09:00:00+00:00")
    add(store, "mentor", "My internship mentor is Priya.", "2026-09-05T09:00:00+00:00")
    trace = DecisionTrace()

    def select_sources(_system: str, _prompt: str) -> str:
        return '{"selected_ids":["offer","mentor"],"reason":"Both are source notes; question is an echo."}'

    result = run_dictation(
        store=store,
        lexical_store=LexicalStore(tmp_path / "find.sqlite3"),
        memory=None,
        user_id="u",
        canonical="Show me what I said about the internship.",
        text_llm=None,
        selection_llm=select_sources,
        trace=trace,
    )
    assert trace.decision == "answer"
    assert trace.selected_dictation_id == "offer"
    assert "I used these relevant notes:" in result[0]
    assert "offer starts" in result[0]
    assert "mentor is Priya" in result[0]
    assert "What did I say" not in result[0]


def test_find_uses_raw_message_not_lexical_canonical(
    store: DictationStore, tmp_path: Path
):
    """FTS runs on the user's wording so alias tokens still match stored notes."""
    add(
        store,
        "hist_506",
        "Planning a short weekend trip to Trivandrum in November.",
        "2026-08-19T14:00:00+00:00",
    )
    add(
        store,
        "lexical_005",
        "Please use Thiruvananthapuram instead of Trivandrum.",
        "2026-08-20T20:10:00+00:00",
    )
    lex = LexicalStore(tmp_path / "lex.sqlite3")
    lex.upsert_mapping(
        "u",
        LexicalMapping(alias="Trivandrum", canonical="Thiruvananthapuram", kind="terminology"),
        source_interaction_id="lexical_005",
    )
    raw = (
        "Find my dictation from August 19, 2026 around 2 PM about my trip to "
        "Trivandrum and polish it using my place-name preferences."
    )
    canonical = raw.replace("Trivandrum", "Thiruvananthapuram")
    trace = DecisionTrace()
    result = run_dictation(
        store=store,
        lexical_store=lex,
        memory=None,
        user_id="u",
        canonical=canonical,
        raw=raw,
        text_llm=None,
        trace=trace,
    )
    assert trace.decision == "answer"
    assert trace.selected_dictation_id == "hist_506"
    assert "Thiruvananthapuram" in result[0]
    assert "Trivandrum" not in result[0]


def test_lexical_teaching_rows_rank_after_content_notes(store: DictationStore, tmp_path: Path):
    """Preference-teaching dictations should not win over substantive notes."""
    add(store, "hist_506", "Planning a trip to Trivandrum.", "2026-08-19T14:00:00+00:00")
    add(
        store,
        "lexical_005",
        "Please use Thiruvananthapuram instead of Trivandrum.",
        "2026-08-20T20:10:00+00:00",
    )
    trace = DecisionTrace()
    result = run_dictation(
        store=store,
        lexical_store=LexicalStore(tmp_path / "lex.sqlite3"),
        memory=None,
        user_id="u",
        canonical="Find my note that mentions Trivandrum and polish it.",
        raw="Find my note that mentions Trivandrum and polish it.",
        text_llm=None,
        trace=trace,
    )
    assert trace.selected_dictation_id == "hist_506"
    assert "lexical_005" not in result[0]


def test_llm_selector_receives_deeper_candidate_pool_than_display_limit():
    """Later query echoes cannot hide an older source note from LLM selection."""
    candidates = [
        {
            "id": f"query_{index}",
            "created_at": "2026-09-07T12:00:00+00:00",
            "formatted_preview": "Find my favourite quote.",
        }
        for index in range(12)
    ]
    candidates.append(
        {
            "id": "source_quote",
            "created_at": "2026-09-07T11:58:32+00:00",
            "formatted_preview": 'My favourite quote is: "Life comes from you and not at you."',
        }
    )
    selected, meta = select_ambiguous_dictation(
        query="Show me my favourite quote.",
        candidates=candidates,
        selection_llm=lambda _s, _p: '{"selected_ids":["source_quote"],"reason":"source"}',
    )
    assert selected == ["source_quote"]
    assert meta["source"] == "llm"
    assert len(candidates) > 5
