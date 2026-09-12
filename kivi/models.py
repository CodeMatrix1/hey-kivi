"""Typed memory schemas: Hindsight semantic types + Kivi lexical mappings."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


MemoryType = Literal["Fact", "Preference", "Episode"]
MemoryStatus = Literal["active", "superseded"]
LexicalKind = Literal["name", "spelling", "alias", "terminology"]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class LexicalMapping(BaseModel):
    alias: str
    canonical: str
    kind: LexicalKind = "alias"


class LexicalExtraction(BaseModel):
    mappings: list[LexicalMapping] = Field(default_factory=list)


class MemoryBase(BaseModel):
    id: str = Field(default_factory=lambda: f"m_{uuid4().hex[:12]}")
    type: MemoryType
    text: str
    source: str = "explicit_user_statement"
    created_at: str = Field(default_factory=utc_now_iso)
    status: MemoryStatus = "active"
    provenance_interaction_id: str | None = None
    user_id: str = ""

    def to_retain_payload(self) -> str:
        """Serialize for Hindsight content (typed header + text)."""
        header = (
            f"[KIVI_MEMORY type={self.type} id={self.id} status={self.status} "
            f"source={self.source} created_at={self.created_at}]"
        )
        return f"{header}\n{self.text}"


class PreferenceMemory(MemoryBase):
    """Used by seed/evals when retaining typed Preference payloads into Hindsight."""

    type: Literal["Preference"] = "Preference"
    surface: str | None = None
    preferred: str | None = None
    preference_kind: Literal["lexical", "other"] = "other"


class FactMemory(MemoryBase):
    """Used by seed/evals when retaining typed Fact payloads into Hindsight."""

    type: Literal["Fact"] = "Fact"
    subject: str | None = None
    predicate: str | None = None
    object: str | None = None


class EpisodeMemory(MemoryBase):
    """Used by seed/evals when retaining typed Episode payloads into Hindsight."""

    type: Literal["Episode"] = "Episode"
    approx_time: str | None = None
    related_dictation_id: str | None = None


class DictationRecord(BaseModel):
    id: str
    user_id: str
    asr: str
    formatted: str
    created_at: str


class DecisionTrace(BaseModel):
    """Inspectable per-turn pipeline decisions for the chat UI and evals."""

    # Interpret flags (routing)
    wants_dictation: bool = False
    wants_cross_recall: bool = False

    # Lexical store (SQLite) — alias→canonical mappings
    memories_retained: list[dict[str, Any]] = Field(default_factory=list)
    memories_ignored: list[dict[str, Any]] = Field(default_factory=list)
    memories_updated: list[dict[str, Any]] = Field(default_factory=list)
    applied_preferences: list[dict[str, str]] = Field(default_factory=list)

    # Hindsight semantic retain / recall
    semantic_retain: bool = False
    semantic_retain_preview: str | None = None
    memories_considered: list[dict[str, Any]] = Field(default_factory=list)
    retrieval_backend: Literal["hindsight", "none"] = "none"
    retrieval_query: str | None = None

    # Dictation find / polish
    candidates: list[dict[str, Any]] = Field(default_factory=list)
    selected_dictation_id: str | None = None
    selected_dictation_ids: list[str] = Field(default_factory=list)
    find_query: dict[str, Any] | None = None
    # Dictation created from this chat turn's user message (always set on chat)
    source_dictation_id: str | None = None

    # Outcome
    source_interactions: list[str] = Field(default_factory=list)
    tools_used: list[str] = Field(default_factory=list)
    decision: Literal["answer", "abstain"] = "answer"
    reason: str = ""
    canonicalized_message: str | None = None

    # Per-step LLM (or rules/fallback) outputs for the decision trace UI
    # Each item: {step, source: llm|rules|fallback|skipped, output}
    llm_calls: list[dict[str, Any]] = Field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()


class ChatResult(BaseModel):
    reply: str
    trace: DecisionTrace

    def to_dict(self) -> dict[str, Any]:
        return {"reply": self.reply, "trace": self.trace.to_dict()}
