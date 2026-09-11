"""Hey Kivi agent: orchestrates turn capabilities."""

from __future__ import annotations
import os

from datetime import datetime, timezone
from typing import Any

from hindsight_pipeline_2.kivi.capabilities import (
    apply_interpret_to_trace,
    interpret_turn,
    run_cross_recall,
    run_dictation,
    run_general_chat,
    run_lexical_learn,
    run_semantic_retain,
)
from hindsight_pipeline_2.kivi.config import Settings
from hindsight_pipeline_2.kivi.storage.dictation_store import DictationStore
from hindsight_pipeline_2.kivi.memory.hindsight_adapter import get_memory_backend
from hindsight_pipeline_2.kivi.storage.lexical_bootstrap import ensure_corpus_lexical_bootstrapped
from hindsight_pipeline_2.kivi.storage.lexical_store import LexicalStore
from hindsight_pipeline_2.kivi.llm import create_generator, create_text_generator
from hindsight_pipeline_2.kivi.models import ChatResult, DecisionTrace, DictationRecord


class HeyKiviAgent:
    def __init__(
        self,
        *,
        settings: Settings | None = None,
        store: DictationStore | None = None,
        lexical_store: LexicalStore | None = None,
        memory_backend: Any | None = None,
        require_llm: bool = True,
        json_llm: Any | None = None,
        text_llm: Any | None = None,
        lexical_llm: Any | None = None,
    ):
        self.settings = settings or Settings.from_env()
        self.save_chats = os.getenv("KIVI_SAVE_CHATS", "true").strip().lower() not in {"0", "false", "off"}
        self.store = store or DictationStore(self.settings.db_path)
        self.lexical_store = lexical_store or LexicalStore(self.settings.db_path)
        self.memory = memory_backend or get_memory_backend(self.settings)
        self.json_llm = json_llm
        self.text_llm = text_llm
        self.lexical_llm = lexical_llm
        if require_llm and self.json_llm is None:
            try:
                self.json_llm = create_generator(self.settings)
                self.text_llm = create_text_generator(self.settings)
                self.lexical_llm = self.json_llm
            except Exception:
                self.json_llm = None
                self.text_llm = None
                self.lexical_llm = None
        elif self.lexical_llm is None:
            self.lexical_llm = self.json_llm

    def close(self) -> None:
        close = getattr(self.memory, "close", None)
        if callable(close):
            close()

    def chat(self, user_id: str, message: str) -> ChatResult:
        """Orchestrate: dictation log → lexical → retain → interpret → tools."""
        ensure_corpus_lexical_bootstrapped(
            user_id, store=self.store, lexical_store=self.lexical_store
        )
        raw = message
        interaction_id = self.store.log_interaction(user_id, "user", raw)
        created_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        if self.save_chats:
            # Every user chat turn is also a DictationRecord (source of truth for find/provenance).
            dictation_id = f"d_chat_{interaction_id}"
            self.store.add_dictation(
                DictationRecord(
                    id=dictation_id,
                    user_id=user_id,
                    asr=raw,
                    formatted=raw,
                    created_at=created_at,
                )
            )
            trace = DecisionTrace(
                source_interactions=[interaction_id],
                source_dictation_id=dictation_id,
            )
            canonical, lex_parts = run_lexical_learn(
                user_id=user_id,
                raw=raw,
                interaction_id=interaction_id,
                lexical_store=self.lexical_store,
                lexical_llm=self.lexical_llm,
                trace=trace,
            )
            parts: list[str] = []
            parts.extend(lex_parts)

            run_semantic_retain(
                memory=self.memory,
                user_id=user_id,
                canonical=canonical,
                trace=trace,
                source_dictation_id=dictation_id,
                created_at=created_at,
            )
        else:
            trace = DecisionTrace(
                source_interactions=[interaction_id],
                source_dictation_id=None,
            )
            parts: list[str] = []
            # Still run lexical learn so any explicit mappings are recorded,
            # but skip dictation retention + semantic retain.
            canonical, lex_parts = run_lexical_learn(
                user_id=user_id,
                raw=raw,
                interaction_id=interaction_id,
                lexical_store=self.lexical_store,
                lexical_llm=self.lexical_llm,
                trace=trace,
            )
            parts.extend(lex_parts)

        intent = interpret_turn(canonical, self.json_llm)
        apply_interpret_to_trace(trace, intent)

        if intent.get("wants_cross_recall"):
            parts.extend(
                run_cross_recall(
                    memory=self.memory,
                    user_id=user_id,
                    raw=raw,
                    canonical=canonical,
                    text_llm=self.text_llm,
                    selection_llm=self.json_llm,
                    store=self.store,
                    trace=trace,
                )
            )

        if intent.get("wants_dictation"):
            parts.extend(
                run_dictation(
                    store=self.store,
                    lexical_store=self.lexical_store,
                    memory=self.memory,
                    user_id=user_id,
                    canonical=canonical,
                    raw=raw,
                    text_llm=self.text_llm,
                    selection_llm=self.json_llm,
                    trace=trace,
                )
            )

        if not intent.get("wants_cross_recall") and not intent.get("wants_dictation"):
            parts.extend(
                run_general_chat(
                    message=canonical,
                    text_llm=self.text_llm,
                    trace=trace,
                    lexical_notes=lex_parts,
                )
            )

        reply = "\n\n".join(parts) if parts else "How can I help you?"
        self.store.log_interaction(user_id, "assistant", reply)
        return ChatResult(reply=reply, trace=trace)


def chat(user_id: str, message: str, **kwargs: Any) -> dict[str, Any]:
    agent = HeyKiviAgent(**kwargs)
    try:
        return agent.chat(user_id, message).to_dict()
    finally:
        agent.close()
