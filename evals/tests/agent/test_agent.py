"""Agent tests — full ``HeyKiviAgent.chat`` turn contracts.

Tier: agent (offline stub memory + seeded demo dictations)

Tests:
- test_lexical_boundary_replace — ``apply_lexical`` replaces complete alias tokens only (word-boundary safe)
- test_semantic_retain_on_smalltalk — general chat retains to Hindsight (``kivi_chat``) without a dictation row
- test_cross_recall_skips_semantic_retain — recall queries do not retain chat turns
- test_find_dictation_skips_semantic_retain — find/polish tool turns do not retain chat turns
- test_chat_retain_then_recall — statement retained on turn 1; recall on turn 2 skips retain but surfaces content
- test_kivi_chat_false_skips_retain — ``KIVI_CHAT=false`` skips Hindsight retain
- test_memory_card_extracts_source_dictation_id — retain header stripped from card text; ``source_dictation_id`` exposed
- test_build_turn_metrics_counts_db_growth — ``build_turn_metrics`` reports elapsed_ms, llm_call_count, retain_call_count, db_delta
- test_cross_recall_memory_cards_include_source_dictation_id — Maya cross-recall cards link back to ``d_corpus_maya``
"""

from __future__ import annotations

import pytest

from hindsight_pipeline_2.kivi.agent import HeyKiviAgent
from hindsight_pipeline_2.kivi.capabilities.trace_utils import memory_card
from hindsight_pipeline_2.kivi.config import Settings
from hindsight_pipeline_2.kivi.instrumentation import MetricsTimer, build_turn_metrics, sqlite_counts
from hindsight_pipeline_2.kivi.lexical.lexical_extract import scripted_lexical_llm
from hindsight_pipeline_2.kivi.models import DictationRecord, FactMemory
from hindsight_pipeline_2.kivi.memory.stub_memory import retain_typed, StubMemory
from hindsight_pipeline_2.kivi.storage.dictation_store import DictationStore
from hindsight_pipeline_2.kivi.storage.lexical import apply_lexical
from hindsight_pipeline_2.kivi.storage.lexical_store import LexicalStore


def test_lexical_boundary_replace():
    """The legacy lexical helper replaces complete alias tokens only."""
    out, n = apply_lexical("Talk to Aditya about Aditya.", "Aditya", "Aaditya")
    assert n == 2
    assert out == "Talk to Aaditya about Aaditya."


def test_semantic_retain_on_smalltalk(agent: HeyKiviAgent):
    """Chat turns retain to Hindsight but are not stored as dictations."""
    before = len(agent.memory.list_memories("demo_user"))
    before_dicts = len(agent.store.list_for_user("demo_user"))
    result = agent.chat("demo_user", "hello there")
    assert result.trace.semantic_retain is True
    after = len(agent.memory.list_memories("demo_user"))
    assert after >= before
    assert result.trace.memories_retained == []
    assert result.trace.wants_dictation is False
    assert result.trace.wants_cross_recall is False
    assert result.trace.source_dictation_id is None
    assert result.trace.source_interactions
    retained = agent.memory._banks["demo_user"][-1]
    assert retained["metadata"].get("kivi_chat") is True
    assert "kivi_chat=true" in retained["text"]
    assert len(agent.store.list_for_user("demo_user")) == before_dicts
    assert "how can i help you" in result.reply.lower()
    assert any(c.get("step") == "general_chat" for c in result.trace.llm_calls)


def test_cross_recall_skips_semantic_retain(agent: HeyKiviAgent):
    """Cross-recall queries must not pollute memory with echoed query text."""
    user_id = "demo_user"
    before = len(agent.memory.list_memories(user_id))
    result = agent.chat(user_id, "What have I been working on for the Kivi meeting?")
    assert result.trace.wants_cross_recall is True
    assert result.trace.semantic_retain is False
    assert len(agent.memory.list_memories(user_id)) == before
    assert "hindsight_recall" in result.trace.tools_used


def test_find_dictation_skips_semantic_retain(agent: HeyKiviAgent):
    """Find/polish dictation turns use tools only — no chat retain."""
    user_id = "demo_user"
    before_mem = len(agent.memory.list_memories(user_id))
    before_dicts = len(agent.store.list_for_user(user_id))
    result = agent.chat(user_id, "Find my Slack dictation about API rate limits.")
    assert result.trace.wants_dictation is True
    assert result.trace.semantic_retain is False
    assert len(agent.memory.list_memories(user_id)) == before_mem
    assert len(agent.store.list_for_user(user_id)) == before_dicts
    assert "find_dictations" in result.trace.tools_used


def test_chat_retain_then_recall(agent: HeyKiviAgent):
    """Substantive chat is retained; a later recall turn does not add another retain."""
    user_id = "retain_recall_user"
    before = len(agent.memory.list_memories(user_id))
    first = agent.chat(user_id, "I am working on the payment reconciliation service.")
    assert first.trace.semantic_retain is True
    assert first.trace.wants_cross_recall is False
    assert len(agent.memory.list_memories(user_id)) > before

    mem_before_recall = len(agent.memory.list_memories(user_id))
    second = agent.chat(user_id, "What did I say about payment reconciliation?")
    assert second.trace.wants_cross_recall is True
    assert second.trace.semantic_retain is False
    assert len(agent.memory.list_memories(user_id)) == mem_before_recall
    considered = " ".join(
        str(card.get("text", "")) for card in (second.trace.memories_considered or [])
    )
    combo = f"{second.reply}\n{considered}".lower()
    assert "payment" in combo or "reconciliation" in combo


def test_kivi_chat_false_skips_retain(no_save_agent: HeyKiviAgent):
    before_dicts = len(no_save_agent.store.list_for_user("u1"))
    before_mem = len(no_save_agent.memory.list_memories("u1"))
    result = no_save_agent.chat("u1", "hello there")
    assert result.trace.source_dictation_id is None
    assert result.trace.semantic_retain is False
    assert len(no_save_agent.store.list_for_user("u1")) == before_dicts
    assert len(no_save_agent.memory.list_memories("u1")) == before_mem


def test_kivi_chat_env_enables_retain_without_dictation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("KIVI_CHAT", "true")
    db = tmp_path / "kivi_chat.sqlite3"
    settings = Settings(
        hindsight_base_url="http://localhost:8888",
        hindsight_api_key=None,
        bank_prefix="kivi2chat",
        memory_backend="hindsight",
        llm_provider="groq",
        db_path=db,
        recall_budget="mid",
    )
    memory = StubMemory()
    agent = HeyKiviAgent(
        settings=settings,
        store=DictationStore(db),
        lexical_store=LexicalStore(db),
        memory_backend=memory,
        require_llm=False,
        json_llm=None,
        text_llm=None,
        lexical_llm=scripted_lexical_llm({"mappings": []}),
    )
    try:
        before_dicts = len(agent.store.list_for_user("u1"))
        result = agent.chat("u1", "I prefer morning standups")
        assert result.trace.semantic_retain is True
        assert result.trace.source_dictation_id is None
        assert len(agent.store.list_for_user("u1")) == before_dicts
        retained = memory._banks["u1"][-1]
        assert retained["metadata"].get("kivi_chat") is True
        assert "kivi_chat=true" in retained["text"]
        assert "source_interaction_id=" in retained["text"]
    finally:
        agent.close()


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
    assert metrics["db_delta"]["dictations"] == 0
    assert metrics["db_delta"]["interactions"] >= 1


def test_agent_runs_both_recall_and_find_when_both_flags(tmp_path):
    """Combined find-note + summarize routes through cross-recall and dictation tools."""
    db = tmp_path / "dual.sqlite3"
    settings = Settings(
        hindsight_base_url="http://localhost:8888",
        hindsight_api_key=None,
        bank_prefix="kivi2dual",
        memory_backend="hindsight",
        llm_provider="groq",
        db_path=db,
        recall_budget="mid",
        default_user_id="u_dual",
    )
    store = DictationStore(db)
    store.add_dictation(
        DictationRecord(
            id="d_payments_note",
            user_id="u_dual",
            asr="payments team review presentation slides deck",
            formatted="Payments team review — presentation slides and deck prep.",
            created_at="2026-09-10T14:00:00+00:00",
        )
    )
    memory = StubMemory()
    retain_typed(
        memory,
        "u_dual",
        FactMemory(
            id="f_payments",
            text="Payments team review and presentation prep notes.",
            source="seed",
            user_id="u_dual",
        ),
    )

    def grounded(_system: str, _user: str) -> str:
        return "You discussed the payments team review and presentation prep."

    agent = HeyKiviAgent(
        settings=settings,
        store=store,
        lexical_store=LexicalStore(db),
        memory_backend=memory,
        require_llm=False,
        json_llm=None,
        text_llm=grounded,
        lexical_llm=scripted_lexical_llm({"mappings": []}),
    )
    try:
        result = agent.chat(
            "u_dual",
            "Find my note about the payments review and summarize what I've said about it.",
        )
    finally:
        agent.close()

    assert result.trace.wants_dictation is True
    assert result.trace.wants_cross_recall is True
    assert result.trace.semantic_retain is False
    assert "hindsight_recall" in result.trace.tools_used
    assert "find_dictations" in result.trace.tools_used


def test_cross_recall_answers_from_session_context_without_hindsight_hit(agent: HeyKiviAgent):
    """Same-conversation user facts should answer recall questions via context_messages."""
    context = [
        {"role": "user", "content": "I am preparing for an exam in biology. I am a student at IITM."},
        {"role": "assistant", "content": "Good luck with your biology exam!"},
    ]

    def grounded(_system: str, user: str) -> str:
        if "biology" in user.lower():
            return "You are preparing for a biology exam."
        return "Okay."

    agent.text_llm = grounded
    result = agent.chat(
        "demo_user",
        "What exam am I preparing for?",
        context_messages=context,
    )
    assert result.trace.wants_cross_recall is True
    assert result.trace.decision == "answer"
    assert "biology" in result.reply.lower()


def test_cross_recall_memory_cards_include_source_dictation_id(agent: HeyKiviAgent):
    result = agent.chat(user_id="demo_user", message="What did I tell you about my sister Maya?")
    assert result.trace.memories_considered
    assert any(
        card.get("source_dictation_id") == "d_corpus_maya"
        for card in result.trace.memories_considered
    )
