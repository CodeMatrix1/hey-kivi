"""Unit tests for eval expectation helpers (seed memory paraphrase checks)."""

from __future__ import annotations

from hindsight_pipeline_2.evals.runners.expect import check_expect


def test_seed_filter_ignores_kivi_chat_memories():
    """Chat-retained memories must not count as seeded memories for paraphrase checks."""
    fails = check_expect(
        {"seed_memories_must_not_contain": ["kivi meeting"]},
        reply="Backend auth refactor.",
        trace={"tools_used": ["hindsight_recall"], "memories_considered": [{"text": "auth"}]},
        seeded_memory_texts=[
            "[source_interaction_id=i_abc kivi_chat=true created_at=2026-09-12 user_id=u1]\n"
            "What have I been working on for the Kivi meeting?",
            "[source_dictation_id=d_slack_1700 created_at=2026-09-04 user_id=u1]\n"
            "Slack dump about API rate limits.",
        ],
    )
    assert fails == []


def test_seed_filter_flags_forbidden_phrase_in_seed_memory():
    fails = check_expect(
        {"seed_memories_must_not_contain": ["kivi meeting"]},
        reply="ok",
        trace={},
        seeded_memory_texts=[
            "[KIVI_MEMORY type=Fact source=seed id=f_bad]\nNotes for the Kivi meeting prep.",
        ],
    )
    assert any("forbidden paraphrase phrase" in f for f in fails)


def test_seed_filter_skips_dictation_provenance_memories():
    fails = check_expect(
        {"seed_memories_must_not_contain": ["kivi meeting"]},
        reply="ok",
        trace={},
        seeded_memory_texts=[
            "[source_dictation_id=d_bad created_at=2026-09-04 user_id=u1]\n"
            "Notes for the Kivi meeting prep.",
        ],
    )
    assert fails == []
