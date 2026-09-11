"""Integrity contracts for Hey Kivi — call real pipeline functions.

Uses: retain_typed, recall, LexicalStore, extract/validate lexical,
find_dictations, polish_dictation, HeyKiviAgent.chat
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from hindsight_pipeline_2.kivi.agent import HeyKiviAgent
from hindsight_pipeline_2.kivi.config import Settings
from hindsight_pipeline_2.kivi.storage.dictation_store import DictationStore
from hindsight_pipeline_2.kivi.memory.stub_memory import StubMemory, retain_typed
from hindsight_pipeline_2.kivi.storage.lexical import resolve_lexical_mappings
from hindsight_pipeline_2.kivi.lexical.lexical_extract import (
    extract_lexical_mappings,
    scripted_lexical_llm,
    validate_lexical_extraction,
)
from hindsight_pipeline_2.kivi.storage.lexical_store import LexicalStore
from hindsight_pipeline_2.kivi.models import DictationRecord, FactMemory, LexicalMapping
from hindsight_pipeline_2.kivi.tools import find_dictations, polish_dictation

from hindsight_pipeline_2.evals.paths import INTEGRITY_CASES_PATH

CASES_PATH = INTEGRITY_CASES_PATH


def load_cases(path: Path | None = None) -> list[dict[str, Any]]:
    path = path or CASES_PATH
    with path.open(encoding="utf-8") as handle:
        cases = json.load(handle)
    if not isinstance(cases, list):
        raise ValueError("Integrity cases must be a JSON list.")

    required_by_type = {
        "clean_start": {"user_id", "query"},
        "seed_retain_recall_round_trip": {"user_id", "memory", "query"},
        "cross_user_isolation": {"user_a", "user_b", "memory", "query"},
        "cleanup_removes_memory": {"user_id", "memory", "query"},
        "memory_reset": {"user_id", "memories", "query"},
        "persistence_across_agent_restart": {"user_id", "memory", "query"},
        "lexical_validation_precision": {"messages"},
        "learn_lexical_mapping": {"user_id", "message", "scripted_lexical"},
        "never_learn_from_kivi_reply": {"user_id", "message"},
        "find_dictations_pipeline": {"user_id", "dictation", "find"},
        "polish_dictation_pipeline": {"user_id", "dictation", "lexical", "occasion"},
        "chat_uses_find_and_polish": {"user_id", "dictation", "lexical", "message"},
    }
    seen: set[str] = set()
    for case in cases:
        if not isinstance(case, dict) or not case.get("id") or not case.get("type"):
            raise ValueError("Every integrity case needs non-empty 'id' and 'type'.")
        if case["id"] in seen:
            raise ValueError(f"Duplicate integrity case id: {case['id']!r}")
        seen.add(case["id"])
        if case["type"] not in required_by_type:
            raise ValueError(f"Unknown integrity type: {case['type']!r}")
        missing = required_by_type[case["type"]] - case.keys()
        if missing:
            raise ValueError(f"{case['id']!r} missing fields: {sorted(missing)}")
    return cases


def _settings(work_dir: Path, *, bank_prefix: str = "kivi2integrity") -> Settings:
    return Settings(
        hindsight_base_url=os.getenv("HINDSIGHT_BASE_URL", "http://localhost:8888").rstrip("/"),
        hindsight_api_key=os.getenv("HINDSIGHT_API_KEY") or None,
        bank_prefix=bank_prefix,
        memory_backend="hindsight",
        llm_provider=os.getenv("LLM_PROVIDER", "groq").strip().lower() or "groq",
        db_path=work_dir / "integrity.sqlite3",
        recall_budget=os.getenv("HINDSIGHT_RECALL_BUDGET", "mid"),
    )


def make_harness(work_dir: Path, *, bank_prefix: str | None = None) -> dict[str, Any]:
    settings = _settings(
        work_dir,
        bank_prefix=bank_prefix or f"kivi2integrity_{os.getpid()}",
    )
    store = DictationStore(settings.db_path)
    lexical_store = LexicalStore(settings.db_path)
    memory = StubMemory()
    agent = HeyKiviAgent(
        settings=settings,
        store=store,
        lexical_store=lexical_store,
        memory_backend=memory,
        require_llm=False,
        json_llm=None,
        text_llm=None,
        lexical_llm=scripted_lexical_llm({"mappings": []}),
    )
    return {
        "settings": settings,
        "store": store,
        "lexical_store": lexical_store,
        "memory": memory,
        "agent": agent,
    }


def _memory_id(item: dict[str, Any]) -> str | None:
    mid = item.get("id")
    if mid:
        return str(mid)
    meta = item.get("metadata") or {}
    if isinstance(meta, dict) and meta.get("id"):
        return str(meta["id"])
    return None


def _texts(items: list[dict[str, Any]]) -> list[str]:
    return [str(i.get("text") or "") for i in items]


def _contains_id(items: list[dict[str, Any]], expected_id: str) -> bool:
    return any(_memory_id(i) == expected_id for i in items)


def _contains_text_fragment(items: list[dict[str, Any]], fragment: str) -> bool:
    frag = fragment.lower()
    return any(frag in t.lower() for t in _texts(items))


def _build_fact(raw: dict[str, Any]) -> FactMemory:
    return FactMemory(
        id=raw["id"],
        text=raw.get("text") or raw.get("content") or "",
        subject=raw.get("subject"),
        predicate=raw.get("predicate"),
        object=raw.get("object"),
        source=raw.get("source", "seed"),
    )


def _seed_memory(memory: Any, user_id: str, raw: dict[str, Any]) -> Any:
    content = raw.get("content") or raw.get("text") or ""
    mem = _build_fact({**raw, "text": content, "id": raw["id"]})
    mem.user_id = user_id
    return retain_typed(memory, user_id, mem)


def users_to_cleanup(case: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for key in ("user_id", "user_a", "user_b"):
        val = case.get(key)
        if isinstance(val, str):
            out.append(val)
    return out


def cleanup_users(harness: dict[str, Any], users: list[str]) -> None:
    memory = harness["memory"]
    store: DictationStore = harness["store"]
    lex: LexicalStore = harness["lexical_store"]
    for user_id in users:
        try:
            memory.reset(user_id)
        except Exception:  # noqa: BLE001
            pass
        store.clear_user(user_id)
        lex.clear_user(user_id)


def check_clean_start(harness: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    memory = harness["memory"]
    recalled = memory.recall(case["user_id"], case["query"], limit=20)
    listed = memory.list_memories(case["user_id"])
    return {
        "passed": not recalled and not listed,
        "recall_count": len(recalled),
        "list_count": len(listed),
    }


def check_seed_retain_recall_round_trip(
    harness: dict[str, Any], case: dict[str, Any]
) -> dict[str, Any]:
    memory = harness["memory"]
    add_result = _seed_memory(memory, case["user_id"], case["memory"])
    recalled = memory.recall(case["user_id"], case["query"], limit=20)
    expected_id = case["memory"]["id"]
    return {
        "passed": _contains_id(recalled, expected_id)
        or _contains_text_fragment(
            recalled, case["memory"].get("content") or case["memory"].get("text", "")
        ),
        "retain_result": add_result,
        "expected_memory_id": expected_id,
        "recalled_ids": [_memory_id(i) for i in recalled],
        "recall_count": len(recalled),
    }


def check_cross_user_isolation(harness: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    memory = harness["memory"]
    add_result = _seed_memory(memory, case["user_a"], case["memory"])
    leaked = memory.recall(case["user_b"], case["query"], limit=20)
    expected_id = case["memory"]["id"]
    leaked_hit = _contains_id(leaked, expected_id) or _contains_text_fragment(
        leaked, case["memory"].get("content") or case["memory"].get("text", "")
    )
    return {
        "passed": not leaked_hit,
        "retain_result": add_result,
        "user_b_recall_count": len(leaked),
        "leaked": leaked_hit,
    }


def check_cleanup_removes_memory(harness: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    memory = harness["memory"]
    add_result = _seed_memory(memory, case["user_id"], case["memory"])
    before = memory.recall(case["user_id"], case["query"], limit=20)
    memory.reset(case["user_id"])
    after = memory.recall(case["user_id"], case["query"], limit=20)
    expected_id = case["memory"]["id"]
    had_before = _contains_id(before, expected_id) or _contains_text_fragment(
        before, case["memory"].get("content") or case["memory"].get("text", "")
    )
    return {
        "passed": had_before and not after,
        "retain_result": add_result,
        "before_count": len(before),
        "after_count": len(after),
    }


def check_memory_reset(harness: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    memory = harness["memory"]
    for raw in case["memories"]:
        _seed_memory(memory, case["user_id"], raw)
    before = memory.recall(case["user_id"], case["query"], limit=50)
    memory.reset(case["user_id"])
    after = memory.recall(case["user_id"], case["query"], limit=50)
    return {
        "passed": len(before) >= len(case["memories"]) and not after,
        "before_count": len(before),
        "after_count": len(after),
    }


def check_persistence_across_agent_restart(
    harness: dict[str, Any], case: dict[str, Any]
) -> dict[str, Any]:
    memory = harness["memory"]
    store = harness["store"]
    lex = harness["lexical_store"]
    settings = harness["settings"]
    add_result = _seed_memory(memory, case["user_id"], case["memory"])
    restarted = HeyKiviAgent(
        settings=settings,
        store=store,
        lexical_store=lex,
        memory_backend=memory,
        require_llm=False,
        json_llm=None,
        text_llm=None,
        lexical_llm=scripted_lexical_llm({"mappings": []}),
    )
    recalled = restarted.memory.recall(case["user_id"], case["query"], limit=20)
    expected_id = case["memory"]["id"]
    ok = _contains_id(recalled, expected_id) or _contains_text_fragment(
        recalled, case["memory"].get("content") or case["memory"].get("text", "")
    )
    return {
        "passed": ok,
        "retain_result": add_result,
        "recall_count_after_restart": len(recalled),
        "expected_memory_id": expected_id,
    }


def check_lexical_validation_precision(
    harness: dict[str, Any], case: dict[str, Any]
) -> dict[str, Any]:
    del harness
    results = []
    all_ok = True
    for item in case["messages"]:
        message = item["text"]
        expect_n = int(item.get("expect_mappings", 0))
        scripted = item.get("scripted_lexical") or {"mappings": []}
        proposed = extract_lexical_mappings(
            message, llm=scripted_lexical_llm(scripted)
        )
        validated = validate_lexical_extraction(message, proposed)
        passed = len(validated.mappings) == expect_n
        if not passed:
            all_ok = False
        results.append(
            {
                "message": message,
                "expect_mappings": expect_n,
                "got": len(validated.mappings),
                "passed": passed,
            }
        )
    return {"passed": all_ok, "results": results}


def check_learn_lexical_mapping(harness: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    lex: LexicalStore = harness["lexical_store"]
    settings = harness["settings"]
    store = harness["store"]
    memory = harness["memory"]
    user_id = case["user_id"]
    agent = HeyKiviAgent(
        settings=settings,
        store=store,
        lexical_store=lex,
        memory_backend=memory,
        require_llm=False,
        lexical_llm=scripted_lexical_llm(case["scripted_lexical"]),
    )
    result = agent.chat(user_id, case["message"])
    active = lex.list_active(user_id)
    return {
        "passed": bool(result.trace.memories_retained) and len(active) >= 1,
        "retained": result.trace.memories_retained,
        "active_mappings": [r.to_dict() for r in active],
        "semantic_retain": result.trace.semantic_retain,
    }


def check_never_learn_from_kivi_reply(
    harness: dict[str, Any], case: dict[str, Any]
) -> dict[str, Any]:
    agent: HeyKiviAgent = harness["agent"]
    user_id = case["user_id"]
    result = agent.chat(user_id, case["message"])
    reply = result.reply
    # Assistant reply must not become a lexical mapping
    leak = any(
        reply[:40] in (m.get("alias") or "") or reply[:40] in (m.get("canonical") or "")
        for m in result.trace.memories_retained
        if isinstance(m, dict)
    )
    return {
        "passed": not leak and len(result.trace.memories_retained) == 0,
        "reply_preview": reply[:120],
        "retained_from_chat": result.trace.memories_retained,
        "assistant_leaked": leak,
    }


def check_find_dictations_pipeline(
    harness: dict[str, Any], case: dict[str, Any]
) -> dict[str, Any]:
    store: DictationStore = harness["store"]
    user_id = case["user_id"]
    raw = dict(case["dictation"])
    raw.setdefault("user_id", user_id)
    store.add_dictation(DictationRecord(**raw))
    find_args = case["find"]
    hits = find_dictations(
        store,
        user_id,
        text_query=find_args.get("text_query") or "",
        date_start=find_args.get("date_start"),
        date_end=find_args.get("date_end"),
    )
    expected_id = raw["id"]
    return {
        "passed": any(h.get("id") == expected_id for h in hits),
        "hits": hits,
        "expected_id": expected_id,
    }


def check_polish_dictation_pipeline(
    harness: dict[str, Any], case: dict[str, Any]
) -> dict[str, Any]:
    store: DictationStore = harness["store"]
    memory = harness["memory"]
    lex: LexicalStore = harness["lexical_store"]
    user_id = case["user_id"]
    raw = dict(case["dictation"])
    raw.setdefault("user_id", user_id)
    store.add_dictation(DictationRecord(**raw))
    mapping = LexicalMapping(
        alias=case["lexical"]["alias"],
        canonical=case["lexical"]["canonical"],
        kind=case["lexical"].get("kind", "name"),
    )
    lex.upsert_mapping(user_id, mapping, source_interaction_id="integrity")
    result = polish_dictation(
        store,
        memory,
        user_id,
        raw["id"],
        case["occasion"],
        text_llm=None,
        lexical_store=lex,
    )
    preferred = mapping.canonical
    polished = result.get("polished_text") or ""
    applied = result.get("applied_preferences") or []
    manual, applied_maps = resolve_lexical_mappings(user_id, raw["formatted"], lex)
    applied_ok = any(a.get("preferred") == preferred for a in applied)
    return {
        "passed": (
            result.get("ok") is True
            and preferred in polished
            and applied_ok
            and preferred in manual
            and bool(applied_maps)
        ),
        "polish_result": {
            "ok": result.get("ok"),
            "polished_text": polished,
            "applied_preferences": applied,
        },
        "manual_resolve": manual,
    }


def check_chat_uses_find_and_polish(
    harness: dict[str, Any], case: dict[str, Any]
) -> dict[str, Any]:
    store: DictationStore = harness["store"]
    memory = harness["memory"]
    lex: LexicalStore = harness["lexical_store"]
    settings = harness["settings"]
    user_id = case["user_id"]
    raw = dict(case["dictation"])
    raw.setdefault("user_id", user_id)
    store.add_dictation(DictationRecord(**raw))
    lex.upsert_mapping(
        user_id,
        LexicalMapping(
            alias=case["lexical"]["alias"],
            canonical=case["lexical"]["canonical"],
            kind=case["lexical"].get("kind", "name"),
        ),
    )
    agent = HeyKiviAgent(
        settings=settings,
        store=store,
        lexical_store=lex,
        memory_backend=memory,
        require_llm=False,
        lexical_llm=scripted_lexical_llm({"mappings": []}),
    )
    result = agent.chat(user_id, case["message"])
    tools = result.trace.tools_used
    preferred = case["lexical"]["canonical"]
    return {
        "passed": (
            "find_dictations" in tools
            and "polish_dictation" in tools
            and preferred in result.reply
        ),
        "tools_used": tools,
        "selected_dictation_id": result.trace.selected_dictation_id,
        "applied_preferences": result.trace.applied_preferences,
        "reply_preview": result.reply[:200],
        "decision": result.trace.decision,
    }


CHECKS = {
    "clean_start": check_clean_start,
    "seed_retain_recall_round_trip": check_seed_retain_recall_round_trip,
    "cross_user_isolation": check_cross_user_isolation,
    "cleanup_removes_memory": check_cleanup_removes_memory,
    "memory_reset": check_memory_reset,
    "persistence_across_agent_restart": check_persistence_across_agent_restart,
    "lexical_validation_precision": check_lexical_validation_precision,
    "learn_lexical_mapping": check_learn_lexical_mapping,
    "never_learn_from_kivi_reply": check_never_learn_from_kivi_reply,
    "find_dictations_pipeline": check_find_dictations_pipeline,
    "polish_dictation_pipeline": check_polish_dictation_pipeline,
    "chat_uses_find_and_polish": check_chat_uses_find_and_polish,
}


def run_case(harness: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    outcome: dict[str, Any] = {
        "case_id": case["id"],
        "description": case.get("description"),
        "type": case["type"],
        "passed": False,
        "evidence": {},
        "error": None,
    }
    users = users_to_cleanup(case)
    try:
        cleanup_users(harness, users)
        outcome["evidence"] = CHECKS[case["type"]](harness, case)
        outcome["passed"] = bool(outcome["evidence"].get("passed"))
    except Exception as error:  # noqa: BLE001
        outcome["error"] = f"{type(error).__name__}: {error}"
    finally:
        cleanup_errors = []
        for user_id in users:
            try:
                cleanup_users(harness, [user_id])
            except Exception as error:  # noqa: BLE001
                cleanup_errors.append(f"{user_id}: {type(error).__name__}: {error}")
        if cleanup_errors:
            msg = "Cleanup failed: " + "; ".join(cleanup_errors)
            outcome["error"] = f"{outcome['error']}; {msg}" if outcome["error"] else msg
            outcome["passed"] = False
    outcome["latency_ms"] = round((time.perf_counter() - started) * 1000, 2)
    return outcome


def run_integrity_suite(
    *,
    work_dir: Path,
    cases: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    cases = cases if cases is not None else load_cases()
    harness = make_harness(work_dir)
    results = []
    try:
        for case in cases:
            results.append(run_case(harness, case))
    finally:
        harness["agent"].close()

    passed = sum(1 for r in results if r["passed"])
    return {
        "suite": "integrity",
        "total": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "pass_rate": round(passed / len(results), 3) if results else 0.0,
        "results": results,
    }
