"""Seed SQLite dictations + lexical mappings for demo and evals."""

from __future__ import annotations

import argparse
import os

from hindsight_pipeline_2.kivi.config import Settings
from hindsight_pipeline_2.kivi.storage.dictation_store import DictationStore
from hindsight_pipeline_2.kivi.memory.hindsight_adapter import get_memory_backend
from hindsight_pipeline_2.kivi.storage.lexical_store import LexicalStore
from hindsight_pipeline_2.kivi.models import DictationRecord, EpisodeMemory, FactMemory, LexicalMapping
from hindsight_pipeline_2.kivi.memory.stub_memory import retain_typed

DEMO_USER = "demo_user"


def seed_demo(
    user_id: str = DEMO_USER,
    settings: Settings | None = None,
    *,
    with_hindsight: bool = False,
) -> dict:
    """Reset user SQLite state and load demo dictations + lexical mappings."""
    settings = settings or Settings.from_env()
    store = DictationStore(settings.db_path)
    lex = LexicalStore(settings.db_path)
    store.clear_user(user_id)
    lex.clear_user(user_id)

    dictations = [
        DictationRecord(
            id="d_slack_1700",
            user_id=user_id,
            asr="remind team about api rate limits with aditya before launch",
            formatted="Remind the team about API rate limits with Aditya before launch.",
            created_at="2026-09-04T17:03:00+00:00",
        ),
        DictationRecord(
            id="d_notes_1000",
            user_id=user_id,
            asr="grocery list milk eggs",
            formatted="Grocery list: milk, eggs.",
            created_at="2026-09-04T10:00:00+00:00",
        ),
        DictationRecord(
            id="d_slack_1200",
            user_id=user_id,
            asr="quick standup update on charts",
            formatted="Quick standup update on charts.",
            created_at="2026-09-04T12:05:00+00:00",
        ),
    ]
    for d in dictations:
        store.add_dictation(d)

    lexical = [
        LexicalMapping(alias="Aditya", canonical="Aaditya", kind="name"),
        LexicalMapping(alias="Kiwi", canonical="Kivi", kind="terminology"),
    ]
    for m in lexical:
        lex.upsert_mapping(user_id, m, source_interaction_id="seed")

    memories_seeded = 0
    if with_hindsight:
        try:
            memory = get_memory_backend(settings)
            try:
                memory.reset(user_id)
            except Exception:  # noqa: BLE001
                pass
            memories = [
                FactMemory(
                    id="f_backend_auth",
                    text="Backend auth refactor for next week's product sync.",
                    subject="user",
                    predicate="works_on",
                    object="backend auth refactor",
                    source="seed",
                    user_id=user_id,
                ),
                EpisodeMemory(
                    id="e_rate_limits",
                    text="Slack dump about API rate limits with Aaditya.",
                    approx_time="2026-09-04T17:03:00+00:00",
                    related_dictation_id="d_slack_1700",
                    source="seed",
                    user_id=user_id,
                ),
            ]
            for mem in memories:
                retain_typed(memory, user_id, mem)
            memories_seeded = len(memories)
        except Exception:  # noqa: BLE001 — optional when Hindsight unavailable
            memories_seeded = 0

    return {
        "status": "seeded",
        "user_id": user_id,
        "dictations": len(dictations),
        "lexical_mappings": len(lexical),
        "memories": memories_seeded,
        "db_path": str(settings.db_path),
        "memory_backend": settings.memory_backend,
        "with_hindsight": with_hindsight,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed demo dictations and lexical mappings")
    parser.add_argument("--user-id", default=DEMO_USER)
    parser.add_argument(
        "--with-hindsight",
        action="store_true",
        help="Also retain demo semantic memories to Hindsight when reachable",
    )
    args = parser.parse_args()
    if args.with_hindsight:
        os.environ.setdefault("KIVI_MEMORY_BACKEND", "hindsight")
    print(seed_demo(args.user_id, with_hindsight=args.with_hindsight))


if __name__ == "__main__":
    main()
