"""Unit tests — interpret rules, cross-recall synthesis, and memory provenance.

Tier: unit (offline stub memory)

Tests:
- test_substantive_query_tokens_strips_framing_not_topics — generic stopwords drop recall phrasing; topic tokens remain
- test_is_synthesis_abstention_detects_declined_answers — detects "I don't know" / insufficient-history declines vs grounded answers
- test_cross_recall_abstains_when_synthesis_declines_despite_recall_hits — synthesis decline → abstain even when recall returns memories
- test_cross_recall_answers_when_synthesis_is_grounded — grounded synthesis → answer with recalled facts in reply
- test_resolve_from_embedded_header — ``source_dictation_id`` parsed from retain payload header
- test_resolve_from_corpus_ingestion_memory_id — ``dict_<id>`` memory id resolves via ``corpus_ingestions`` table
- test_memory_card_does_not_infer_dictation_via_fts — memory cards never guess dictation id from FTS text overlap
- test_payments_review_pull_together_triggers_cross_recall — payments-review "pull together" message routes to cross-recall, not find
- test_find_dictation_still_routes_dictation — explicit find/polish dictation request routes to dictation path
- test_what_did_i_tell_triggers_cross_recall — "what did I tell you" questions route to cross-recall
- test_interpret_llm_fallback_routes_cross_recall — interpret LLM failure falls back to rules union and still runs cross-recall
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hindsight_pipeline_2.kivi.agent import HeyKiviAgent
from hindsight_pipeline_2.kivi.capabilities.cross_recall import (
    is_synthesis_abstention,
    is_terse_abstention,
    run_cross_recall,
)
from hindsight_pipeline_2.kivi.query_tokens import substantive_query_tokens
from hindsight_pipeline_2.kivi.capabilities.interpret import interpret_rules, interpret_turn
from hindsight_pipeline_2.kivi.capabilities.trace_utils import memory_card
from hindsight_pipeline_2.kivi.config import Settings
from hindsight_pipeline_2.kivi.storage.dictation_store import DictationStore
from hindsight_pipeline_2.kivi.lexical.lexical_extract import scripted_lexical_llm
from hindsight_pipeline_2.kivi.storage.lexical_store import LexicalStore
from hindsight_pipeline_2.kivi.models import DecisionTrace, DictationRecord, FactMemory
from hindsight_pipeline_2.kivi.memory.stub_memory import StubMemory, retain_typed


def test_substantive_query_tokens_strips_framing_not_topics():
    """Generic scaffolding drops question shape; topic words like Maya or payments stay."""
    assert substantive_query_tokens("What did I tell you about my sister Maya?") == ["sister", "maya"]
    assert substantive_query_tokens(
        "Pull together what I already said about the payments review."
    ) == ["payments", "review"]
    assert substantive_query_tokens("What have I been working on for the Kivi meeting?") == []
    assert substantive_query_tokens("Have I mentioned the Mars colony habitat budget?") == [
        "mars",
        "colony",
        "habitat",
        "budget",
    ]
    assert substantive_query_tokens("What is my passport number?") == ["passport"]


def test_is_synthesis_abstention_detects_declined_answers():
    assert is_synthesis_abstention("I don't know.")
    assert is_synthesis_abstention("I don't have enough in your history to say.")
    assert not is_synthesis_abstention("Maya lives in Pune.")
    assert not is_synthesis_abstention("You told me Maya is your sister and she lives in Pune.")


def test_is_terse_abstention_distinguishes_bare_vs_explanatory_declines():
    assert is_terse_abstention("I don't know.")
    assert not is_terse_abstention(
        "I don't know. The memories indicate that you are considering a short trip to "
        "Jaipur next month, but they do not mention which hotel you are staying at."
    )


def test_cross_recall_abstains_when_synthesis_declines_despite_recall_hits():
    memory = StubMemory()
    user_id = "u_passport"
    retain_typed(
        memory,
        user_id,
        FactMemory(
            id="f_noise",
            text="User had a passing thought number 35.",
            source="seed",
            user_id=user_id,
        ),
    )
    trace = DecisionTrace()

    def deny_answer(_system: str, _user: str) -> str:
        return "I don't know."

    parts = run_cross_recall(
        memory=memory,
        user_id=user_id,
        raw="What is my passport number?",
        canonical="What is my passport number?",
        text_llm=deny_answer,
        trace=trace,
    )

    assert trace.decision == "abstain"
    assert "none support an answer" in trace.reason
    assert trace.memories_considered
    assert (
        "don't know" in parts[0].casefold()
        or "don't have enough in your history" in parts[0].casefold()
    )


def test_cross_recall_keeps_explanatory_abstention_instead_of_bullet_dump():
    memory = StubMemory()
    user_id = "u_hotel"
    retain_typed(
        memory,
        user_id,
        FactMemory(
            id="f_jaipur",
            text="User is considering a short trip to Jaipur next month.",
            source="seed",
            user_id=user_id,
        ),
    )
    trace = DecisionTrace()
    explanatory = (
        "I don't know. The memories indicate that you are considering a short trip to "
        "Jaipur next month, but they do not mention which hotel you are staying at."
    )

    def explain_abstain(_system: str, _user: str) -> str:
        return explanatory

    parts = run_cross_recall(
        memory=memory,
        user_id=user_id,
        raw="Which hotel am I staying at next month?",
        canonical="Which hotel am I staying at next month?",
        text_llm=explain_abstain,
        trace=trace,
    )

    assert trace.decision == "abstain"
    assert "explanation from recalled context" in trace.reason
    assert parts[0] == explanatory
    assert "Based on what you've said before:" not in parts[0]


def test_cross_recall_falls_back_when_synthesis_declines_but_memories_match():
    """On-topic recall with an 'I don't know' synthesis still returns a summary."""
    memory = StubMemory()
    user_id = "u_payments"
    retain_typed(
        memory,
        user_id,
        FactMemory(
            id="f_pay",
            text="User had a project review with the payments team.",
            source="seed",
            user_id=user_id,
        ),
    )
    retain_typed(
        memory,
        user_id,
        FactMemory(
            id="f_pres",
            text="User worked on a presentation for the payments review.",
            source="seed",
            user_id=user_id,
        ),
    )
    trace = DecisionTrace()
    message = (
        "I have a payments team review coming up. Pull together what I have already said "
        "about the review and the presentation work, then give me the key points to bring in."
    )

    def deny_answer(_system: str, _user: str) -> str:
        return "I don't know."

    parts = run_cross_recall(
        memory=memory,
        user_id=user_id,
        raw=message,
        canonical=message,
        text_llm=deny_answer,
        trace=trace,
    )

    assert trace.decision == "answer"
    assert "summarized" in trace.reason
    assert "payments" in parts[0].casefold()
    assert "presentation" in parts[0].casefold()


def test_cross_recall_answers_when_synthesis_is_grounded():
    memory = StubMemory()
    user_id = "u_maya"
    retain_typed(
        memory,
        user_id,
        FactMemory(
            id="f_maya",
            text="Maya is the user's sister and lives in Pune.",
            subject="Maya",
            predicate="lives_in",
            object="Pune",
            source="seed",
            user_id=user_id,
        ),
    )
    trace = DecisionTrace()

    def grounded(_system: str, _user: str) -> str:
        return "Maya lives in Pune."

    parts = run_cross_recall(
        memory=memory,
        user_id=user_id,
        raw="What did I tell you about my sister Maya?",
        canonical="What did I tell you about my sister Maya?",
        text_llm=grounded,
        trace=trace,
    )

    assert trace.decision == "answer"
    assert "synthesized from" in trace.reason
    assert "Pune" in parts[0]


@pytest.fixture()
def provenance_store(tmp_path: Path) -> DictationStore:
    s = DictationStore(tmp_path / "prov.sqlite3")
    s.add_dictation(
        DictationRecord(
            id="hist_001",
            user_id="u",
            asr="my sister maya lives in pune.",
            formatted="My sister Maya lives in Pune.",
            created_at="2026-07-01T07:10:00+00:00",
        )
    )
    s.mark_ingested("u", "hist_001", content_hash="abc", memory_id="dict_hist_001")
    return s


def test_resolve_from_embedded_header(provenance_store: DictationStore):
    text = (
        "[source_dictation_id=hist_421 created_at=2026-08-12T07:10:00+00:00 user_id=u]\n"
        "Payments team review."
    )
    assert provenance_store.resolve_source_dictation("u", text) == "hist_421"


def test_resolve_from_corpus_ingestion_memory_id(provenance_store: DictationStore):
    assert provenance_store.resolve_source_dictation(
        "u",
        "Some extracted Hindsight fact.",
        memory_id="dict_hist_001",
    ) == "hist_001"


def test_memory_card_does_not_infer_dictation_via_fts(provenance_store: DictationStore):
    card = memory_card(
        {
            "id": "157e792e-9d43-428b-8aff-eb0bb38ae004",
            "text": "Maya is the user's sister and lives in Pune.",
        },
        store=provenance_store,
        user_id="u",
    )
    assert "source_dictation_id" not in card


def test_payments_review_pull_together_triggers_cross_recall():
    message = (
        "I have a payments team review coming up. Pull together what I have already said "
        "about the review and the presentation work, then give me the key points to bring in."
    )
    flags = interpret_rules(message)
    assert flags["wants_cross_recall"] is True
    assert flags["wants_dictation"] is False


def test_find_dictation_still_routes_dictation():
    message = "Find my Slack dictation about API rate limits and polish it for the meeting."
    flags = interpret_rules(message)
    assert flags["wants_dictation"] is True


def test_polish_only_stays_dictation_only():
    message = "Polish my Goa note for sharing with a friend."
    flags = interpret_turn(message, json_llm=None)
    assert flags["wants_dictation"] is True
    assert flags["wants_cross_recall"] is False


def test_find_note_with_pull_together_sets_both_flags():
    message = (
        "Find my note about the payments review and summarize what I've said about it."
    )
    flags = interpret_turn(message, json_llm=None)
    assert flags["wants_dictation"] is True
    assert flags["wants_cross_recall"] is True


def test_what_did_i_tell_triggers_cross_recall():
    flags = interpret_rules("What did I tell you about my sister Maya?")
    assert flags["wants_cross_recall"] is True


def test_what_exam_preparing_triggers_cross_recall():
    flags = interpret_rules("What exam am I preparing for?")
    assert flags["wants_cross_recall"] is True


def test_interpret_llm_fallback_routes_cross_recall(tmp_path: Path):
    """When interpret LLM fails, rules union still routes cross-recall."""
    message = (
        "I have a payments team review coming up. Pull together what I have already said "
        "about the review and the presentation work, then give me the key points to bring in."
    )

    def failing_json(_system: str, _prompt: str) -> str:
        raise RuntimeError("interpret unavailable")

    def grounded(_system: str, _user: str) -> str:
        return "You discussed the payments team review and presentation prep."

    db = tmp_path / "routing.sqlite3"
    settings = Settings(
        hindsight_base_url="http://localhost:8888",
        hindsight_api_key=None,
        bank_prefix="kivi2route",
        memory_backend="hindsight",
        llm_provider="groq",
        db_path=db,
        recall_budget="mid",
    )
    memory = StubMemory()
    retain_typed(
        memory,
        "u",
        FactMemory(
            id="f_pay",
            text="Payments team review and presentation prep notes.",
            source="seed",
            user_id="u",
        ),
    )
    agent = HeyKiviAgent(
        settings=settings,
        store=DictationStore(db),
        lexical_store=LexicalStore(db),
        memory_backend=memory,
        require_llm=False,
        json_llm=failing_json,
        text_llm=grounded,
        lexical_llm=scripted_lexical_llm({"mappings": []}),
    )
    try:
        result = agent.chat("u", message)
    finally:
        agent.close()

    interpret_calls = [c for c in result.trace.llm_calls if c.get("step") == "interpret"]
    assert interpret_calls
    assert interpret_calls[0].get("source") == "fallback"
    assert result.trace.wants_cross_recall is True
    assert "hindsight_recall" in result.trace.tools_used
