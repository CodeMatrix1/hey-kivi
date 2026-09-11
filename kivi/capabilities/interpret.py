"""Turn interpreter: decide wants_dictation / wants_cross_recall."""

from __future__ import annotations

import re
from typing import Any

from hindsight_pipeline_2.kivi.capabilities.trace_utils import record_llm
from hindsight_pipeline_2.kivi.config import INTERPRET_SYSTEM
from hindsight_pipeline_2.kivi.llm import llm_json
from hindsight_pipeline_2.kivi.models import DecisionTrace


def interpret_rules(message: str) -> dict[str, Any]:
    """Deterministic fallback when no LLM is available."""
    lower = message.lower()
    wants_dictation = bool(
        re.search(
            r"\b(find|get|fetch|open|show)\b.*\b(dictation|note|slack|message|draft|document)\b",
            lower,
        )
        or re.search(r"\b(polish|rewrite)\b.*\b(dictation|note|slack|message)\b", lower)
        or ("polish" in lower and re.search(r"\b(dictation|note|slack|5\s*pm|meeting)\b", lower))
        or re.search(r"\bdictation\b.*\b(yesterday|slack|pm|am)\b", lower)
    )
    wants_cross = bool(
        re.search(
            r"what have i been working on|what (have|did) i (work|discuss|tell|say|decide)"
            r"|what i (have )?already (said|told|mentioned|discussed)"
            r"|pull together.*(what|said|told|mentioned|already|history|notes)"
            r"|bring together.*(what|said|told|mentioned|history|notes)"
            r"|gather.*(what|said|told|mentioned|already).*(said|told|mentioned|history)"
            r"|(key points|compile|recap).*(what|said|told|mentioned|already|history)"
            r"|remind me (?:what|where|who|which|about)"
            r"|what do you remember|have i mentioned|based on what you know"
            r"|based on what i (have )?(told|said|mentioned|discussed)"
            r"|what (?:food )?preferences have i shared"
            r"|what is my |what's my |which .+ am i "
            r"|what were the options|what was the approach|what did we decide"
            r"|summarize what i('ve| have) (said|told|mentioned|discussed)"
            r"|what kind of .+ would suit me"
            r"|how (?:should|do) you spell my name"
            r"|what have i said about"
            r"|which .+ have i (?:only )?(?:considered|confirmed|booked)"
            r"|did i actually confirm or book"
            r"|what preferences should shape",
            lower,
        )
    )
    return {
        "wants_dictation": wants_dictation,
        "wants_cross_recall": wants_cross,
    }


def _merge_with_rules(llm_flags: dict[str, bool], rules: dict[str, Any]) -> dict[str, bool]:
    """Union LLM flags with deterministic rules so recall requests are not dropped."""
    merged = {
        "wants_dictation": bool(llm_flags.get("wants_dictation")) or bool(rules["wants_dictation"]),
        "wants_cross_recall": bool(llm_flags.get("wants_cross_recall"))
        or bool(rules["wants_cross_recall"]),
    }
    return merged


def _apply_dictation_priority(message: str, flags: dict[str, bool]) -> dict[str, bool]:
    """Find/polish turns use dictation only — cross-recall would duplicate or conflict."""
    lower = message.lower()
    if flags.get("wants_dictation") and re.search(
        r"\b(find|polish|open|show|fetch|get)\b", lower
    ):
        flags["wants_cross_recall"] = False
    return flags


def interpret_turn(message: str, json_llm: Any) -> dict[str, Any]:
    """Return routing flags plus `_llm_source` / `_llm_output` for the trace."""
    rules = interpret_rules(message)
    if json_llm is not None:
        try:
            raw = llm_json(json_llm, INTERPRET_SYSTEM, message)
            merged = _apply_dictation_priority(message, _merge_with_rules(raw, rules))
            return {
                **merged,
                "_llm_source": "llm",
                "_llm_output": raw,
            }
        except Exception as exc:  # noqa: BLE001
            merged = _apply_dictation_priority(message, dict(rules))
            return {
                **merged,
                "_llm_source": "fallback",
                "_llm_output": {
                    "error": str(exc),
                    "wants_dictation": merged["wants_dictation"],
                    "wants_cross_recall": merged["wants_cross_recall"],
                },
            }
    merged = _apply_dictation_priority(message, dict(rules))
    return {
        **merged,
        "_llm_source": "rules",
        "_llm_output": {
            "wants_dictation": merged["wants_dictation"],
            "wants_cross_recall": merged["wants_cross_recall"],
        },
    }


def apply_interpret_to_trace(trace: DecisionTrace, intent: dict[str, Any]) -> None:
    """Copy flags + LLM output onto the decision trace."""
    trace.wants_dictation = bool(intent.get("wants_dictation"))
    trace.wants_cross_recall = bool(intent.get("wants_cross_recall"))
    record_llm(
        trace,
        "interpret",
        source=str(intent.get("_llm_source") or "rules"),
        output=intent.get("_llm_output")
        or {
            "wants_dictation": trace.wants_dictation,
            "wants_cross_recall": trace.wants_cross_recall,
        },
    )
