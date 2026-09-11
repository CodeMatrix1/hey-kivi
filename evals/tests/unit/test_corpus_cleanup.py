"""Unit tests — corpus noise cleanup and lexical bootstrap from corpus rows."""

from __future__ import annotations

from hindsight_pipeline_2.kivi.corpus.lexical_from_corpus import mapping_from_formatted
from hindsight_pipeline_2.kivi.corpus.text_cleanup import strip_corpus_metadata_noise
from hindsight_pipeline_2.kivi.models import DictationRecord
from hindsight_pipeline_2.kivi.storage.dictation_store import DictationStore
from hindsight_pipeline_2.kivi.storage.lexical_bootstrap import ensure_corpus_lexical_bootstrapped
from hindsight_pipeline_2.kivi.storage.lexical_store import LexicalStore


def test_strip_corpus_metadata_noise():
    raw = (
        "I'm planning a weekend in Goa in December. "
        "I was considering it around the 91st planning note."
    )
    assert strip_corpus_metadata_noise(raw) == "I'm planning a weekend in Goa in December."
    review = (
        "I had a project review with the payments team yesterday. "
        "This was part of my activity log entry 41."
    )
    assert "activity log" not in strip_corpus_metadata_noise(review).casefold()


def test_mapping_from_trivandrum_preference():
    mapping = mapping_from_formatted(
        "Please use Thiruvananthapuram instead of Trivandrum."
    )
    assert mapping is not None
    assert mapping.alias == "Trivandrum"
    assert mapping.canonical == "Thiruvananthapuram"


def test_lexical_apply_on_trip_dictation(tmp_path):
    from hindsight_pipeline_2.kivi.tools import polish_dictation

    db = tmp_path / "lex_apply.sqlite3"
    store = DictationStore(db)
    lex = LexicalStore(db)
    store.add_dictation(
        DictationRecord(
            id="hist_506",
            user_id="u",
            asr="planning a short weekend trip to trivandrum in november.",
            formatted="Planning a short weekend trip to Trivandrum in November.",
            created_at="2026-08-19T14:00:00+00:00",
        )
    )
    lex.upsert_mapping(
        "u",
        mapping_from_formatted("Please use Thiruvananthapuram instead of Trivandrum."),
    )
    result = polish_dictation(
        store, None, "u", "hist_506", "general cleanup", text_llm=None, lexical_store=lex
    )
    assert result["ok"]
    assert "Thiruvananthapuram" in result["polished_text"]
    assert "Trivandrum" not in result["polished_text"]
    assert result["applied_preferences"]


def test_bootstrap_lexical_from_corpus_rows(tmp_path):
    db = tmp_path / "boot.sqlite3"
    store = DictationStore(db)
    lex = LexicalStore(db)
    store.add_dictation(
        DictationRecord(
            id="lexical_005",
            user_id="u",
            asr="Please use Thiruvananthapuram instead of Trivandrum.",
            formatted="Please use Thiruvananthapuram instead of Trivandrum.",
            created_at="2026-08-20T20:10:00+00:00",
        )
    )
    added = ensure_corpus_lexical_bootstrapped("u", store=store, lexical_store=lex)
    assert added == 1
    active = lex.list_active("u")
    assert active[0].alias == "Trivandrum"
    assert active[0].canonical == "Thiruvananthapuram"
