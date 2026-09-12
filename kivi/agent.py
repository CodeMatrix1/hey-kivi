"""Hey Kivi agent: orchestrates turn capabilities."""

from __future__ import annotations
import os

from datetime import datetime, timezone
from typing import Any

from hindsight_pipeline_2.kivi.conversation_context import format_continuity_block
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
from hindsight_pipeline_2.kivi.models import ChatResult, DecisionTrace


def _env_flag(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() not in {"0", "false", "off", ""}


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
        # Chat → Hindsight retain only (not dictation rows in SQLite).
        self.kivi_chat = _env_flag("KIVI_CHAT")
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

    def chat(
        self,
        user_id: str,
        message: str,
        context_messages: list[dict[str, str]] | None = None,
    ) -> ChatResult:
        """Orchestrate: dictation log → lexical → retain → interpret → tools."""
        ensure_corpus_lexical_bootstrapped(
            user_id, store=self.store, lexical_store=self.lexical_store
        )
        raw = message
        interaction_id = self.store.log_interaction(user_id, "user", raw)
        created_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        trace = DecisionTrace(
            source_interactions=[interaction_id],
            source_dictation_id=None,
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

        intent = interpret_turn(canonical, self.json_llm)
        apply_interpret_to_trace(trace, intent)

        # Retain substantive chat only — not recall queries or dictation/find tool turns.
        if self.kivi_chat and not intent.get("wants_cross_recall") and not intent.get(
            "wants_dictation"
        ):
            run_semantic_retain(
                memory=self.memory,
                user_id=user_id,
                canonical=canonical,
                trace=trace,
                source_interaction_id=interaction_id,
                created_at=created_at,
                kivi_chat=True,
            )

        continuity_block = (
            format_continuity_block(context_messages, canonical)
            if context_messages
            else None
        )

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
                    continuity_context=continuity_block,
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
            llm_message = continuity_block if continuity_block else canonical
            parts.extend(
                run_general_chat(
                    message=llm_message,
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
