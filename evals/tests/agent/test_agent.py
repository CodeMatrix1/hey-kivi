"""Agent tests — full ``HeyKiviAgent.chat`` turn contracts.

Tier: agent (offline stub memory + seeded demo dictations)

Tests:
- test_lexical_boundary_replace — ``apply_lexical`` replaces complete alias tokens only (word-boundary safe)
- test_semantic_retain_on_smalltalk — smalltalk persists dictation + interaction; semantic retain on; general_chat LLM step
- test_save_chats_false_skips_dictation_and_retain — ``KIVI_SAVE_CHATS=false`` skips dictation row and Hindsight retain
- test_memory_card_extracts_source_dictation_id — retain header stripped from card text; ``source_dictation_id`` exposed
- test_build_turn_metrics_counts_db_growth — ``build_turn_metrics`` reports elapsed_ms, llm_call_count, retain_call_count, db_delta
- test_cross_recall_memory_cards_include_source_dictation_id — Maya cross-recall cards link back to ``d_corpus_maya``
"""

from __future__ import annotations

import pytest

from hindsight_pipeline_2.kivi.agent import HeyKiviAgent
from hindsight_pipeline_2.kivi.capabilities.trace_utils import memory_card
from hindsight_pipeline_2.kivi.instrumentation import MetricsTimer, build_turn_metrics, sqlite_counts
from hindsight_pipeline_2.kivi.storage.lexical import apply_lexical


def test_lexical_boundary_replace():
    """The legacy lexical helper replaces complete alias tokens only."""
    out, n = apply_lexical("Talk to Aditya about Aditya.", "Aditya", "Aaditya")
    assert n == 2
    assert out == "Talk to Aaditya about Aaditya."


def test_semantic_retain_on_smalltalk(agent: HeyKiviAgent):
    """Every chat turn is persisted with provenance even when it is small talk."""
    before = len(agent.memory.list_memories("demo_user"))
    before_dicts = len(agent.store.list_for_user("demo_user"))
    result = agent.chat("demo_user", "hello there")
    assert result.trace.semantic_retain is True
    after = len(agent.memory.list_memories("demo_user"))
    assert after >= before
    assert result.trace.memories_retained == []
    assert result.trace.wants_dictation is False
    assert result.trace.wants_cross_recall is False
    assert result.trace.source_dictation_id
    assert result.trace.source_dictation_id.startswith("d_chat_")
    persisted = agent.store.get("demo_user", result.trace.source_dictation_id)
    assert persisted is not None
    assert persisted.asr == "hello there"
    assert persisted.formatted == "hello there"
    assert len(agent.store.list_for_user("demo_user")) == before_dicts + 1
    assert "how can i help you" in result.reply.lower()
    assert any(c.get("step") == "general_chat" for c in result.trace.llm_calls)


def test_save_chats_false_skips_dictation_and_retain(no_save_agent: HeyKiviAgent):
    before_dicts = len(no_save_agent.store.list_for_user("u1"))
    before_mem = len(no_save_agent.memory.list_memories("u1"))
    result = no_save_agent.chat("u1", "hello there")
    assert result.trace.source_dictation_id is None
    assert result.trace.semantic_retain is False
    assert len(no_save_agent.store.list_for_user("u1")) == before_dicts
    assert len(no_save_agent.memory.list_memories("u1")) == before_mem


def test_memory_card_extracts_source_dictation_id():
    card = memory_card(
        {
            "id": "mem-1",
            "text": (
                "[source_dictation_id=d_smoke_01 created_at=2026-09-02T10:00:00+00:00 "
                "user_id=golden_goose_eval_user]\nMaya lives in Pune."
            ),
        }
    )
    assert card["source_dictation_id"] == "d_smoke_01"
    assert "Maya lives in Pune" in card["text"]
    assert "[source_dictation_id=" not in card["text"]


def test_build_turn_metrics_counts_db_growth(agent: HeyKiviAgent):
    user_id = "demo_user"
    db_before = sqlite_counts(agent.settings.db_path, user_id)
    timer = MetricsTimer()
    result = agent.chat(user_id, "hello there")
    metrics = build_turn_metrics(
        trace=result.trace.to_dict(),
        db_before=db_before,
        db_after=sqlite_counts(agent.settings.db_path, user_id),
        elapsed_ms=timer.elapsed_ms(),
    )
    assert metrics["elapsed_ms"] >= 0
    assert metrics["llm_call_count"] >= 1
    assert metrics["retain_call_count"] == 1
    assert metrics["db_delta"]["dictations"] >= 1
    assert metrics["db_delta"]["interactions"] >= 1


def test_cross_recall_memory_cards_include_source_dictation_id(agent: HeyKiviAgent):
    result = agent.chat(user_id="demo_user", message="What did I tell you about my sister Maya?")
    assert result.trace.memories_considered
    assert any(
        card.get("source_dictation_id") == "d_corpus_maya"
        for card in result.trace.memories_considered
    )
