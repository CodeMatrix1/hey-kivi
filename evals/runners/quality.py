"""Reproducible pipeline quality evals for Hey Kivi Phase 1.

Runs case-driven checks against reply + decision trace (no judge model).

Usage:
    python -m hindsight_pipeline_2.evals.cli.runner
    python -m hindsight_pipeline_2.evals.cli.runner --backend stub
    python -m hindsight_pipeline_2.evals.cli.runner --category retrieval
    python -m hindsight_pipeline_2.evals.cli.runner --case paraphrase-cross-recall
    python -m hindsight_pipeline_2.evals.cli.runner --backend hindsight

Writes: hindsight_pipeline_2/artifacts/evals/last_run.json
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hindsight_pipeline_2.kivi.agent import HeyKiviAgent
from hindsight_pipeline_2.kivi.config import Settings
from hindsight_pipeline_2.kivi.storage.dictation_store import DictationStore
from hindsight_pipeline_2.evals.paths import DEMO_CASES_PATH, LAST_RUN_PATH
from hindsight_pipeline_2.evals.runners.expect import check_expect, load_cases
from hindsight_pipeline_2.kivi.memory.hindsight_adapter import get_memory_backend
from hindsight_pipeline_2.kivi.lexical.lexical_extract import scripted_lexical_llm
from hindsight_pipeline_2.kivi.storage.lexical_store import LexicalStore
from hindsight_pipeline_2.kivi.models import (
    DictationRecord,
    EpisodeMemory,
    FactMemory,
    PreferenceMemory,
)
from hindsight_pipeline_2.kivi.seed import seed_demo
from hindsight_pipeline_2.kivi.memory.stub_memory import StubMemory, retain_typed

CASES_PATH = DEMO_CASES_PATH
REPORT_PATH = LAST_RUN_PATH


def _build_memory(raw: dict[str, Any]):
    mtype = raw.get("type", "Fact")
    common = {
        "id": raw.get("id"),
        "text": raw["text"],
        "source": raw.get("source", "seed"),
        "status": raw.get("status", "active"),
    }
    common = {k: v for k, v in common.items() if v is not None}
    if mtype == "Preference":
        return PreferenceMemory(
            **common,
            surface=raw.get("surface"),
            preferred=raw.get("preferred"),
            preference_kind=raw.get("preference_kind", "lexical"),
        )
    if mtype == "Episode":
        return EpisodeMemory(
            **common,
            approx_time=raw.get("approx_time"),
            related_dictation_id=raw.get("related_dictation_id"),
        )
    return FactMemory(
        **common,
        subject=raw.get("subject"),
        predicate=raw.get("predicate"),
        object=raw.get("object"),
    )


def setup_case(
    case: dict[str, Any],
    *,
    backend_name: str,
    work_dir: Path,
) -> HeyKiviAgent:
    user_id = case["user_id"]
    db_path = work_dir / f"{user_id}.sqlite3"
    settings = Settings(
        hindsight_base_url=os.getenv("HINDSIGHT_BASE_URL", "http://localhost:8888").rstrip(
            "/"
        ),
        hindsight_api_key=os.getenv("HINDSIGHT_API_KEY") or None,
        bank_prefix=f"kivi2eval_{user_id}"[:48],
        memory_backend="hindsight",
        llm_provider=os.getenv("LLM_PROVIDER", "groq").strip().lower() or "groq",
        db_path=db_path,
        recall_budget=os.getenv("HINDSIGHT_RECALL_BUDGET", "mid"),
    )
    store = DictationStore(db_path)
    lexical_store = LexicalStore(db_path)
    if backend_name == "stub":
        memory = StubMemory()
    else:
        memory = get_memory_backend(settings)
        try:
            memory.reset(user_id)
        except Exception:  # noqa: BLE001
            pass
    store.clear_user(user_id)
    lexical_store.clear_user(user_id)

    setup = case.get("setup") or {}
    if setup.get("use_demo_seed"):
        seed_demo(user_id, settings=settings)
        for raw in (
            {
                "type": "Fact",
                "id": "f_backend_auth",
                "text": "Backend auth refactor for next week's product sync.",
                "subject": "user",
                "predicate": "works_on",
                "object": "backend auth refactor",
                "source": "seed",
            },
            {
                "type": "Episode",
                "id": "e_rate_limits",
                "text": "Slack dump about API rate limits with Aaditya.",
                "approx_time": "2026-09-04T17:03:00+00:00",
                "related_dictation_id": "d_slack_1700",
                "source": "seed",
            },
        ):
            mem = _build_memory(raw)
            mem.user_id = user_id
            retain_typed(memory, user_id, mem)
    else:
        for raw in setup.get("dictations") or []:
            payload = dict(raw)
            payload.setdefault("user_id", user_id)
            store.add_dictation(DictationRecord(**payload))
        for raw in setup.get("memories") or []:
            mem = _build_memory(raw)
            mem.user_id = user_id
            retain_typed(memory, user_id, mem)

    scripted = setup.get("scripted_lexical") or {"mappings": []}
    lex_llm = scripted_lexical_llm(scripted)

    return HeyKiviAgent(
        settings=settings,
        store=store,
        lexical_store=lexical_store,
        memory_backend=memory,
        require_llm=False,
        json_llm=None,
        text_llm=None,
        lexical_llm=lex_llm,
    )


def _seeded_texts_from_agent(agent: HeyKiviAgent, user_id: str) -> list[str]:
    try:
        items = agent.memory.list_memories(user_id)
    except Exception:  # noqa: BLE001
        return []
    out: list[str] = []
    for item in items:
        if isinstance(item, dict):
            out.append(str(item.get("text") or ""))
        else:
            out.append(str(item))
    return out


def run_case(case: dict[str, Any], *, backend_name: str, work_dir: Path) -> dict[str, Any]:
    agent = setup_case(case, backend_name=backend_name, work_dir=work_dir)
    user_id = case["user_id"]
    turn_results: list[dict[str, Any]] = []
    all_fails: list[str] = []
    seeded_texts = _seeded_texts_from_agent(agent, user_id)

    try:
        for i, turn in enumerate(case.get("turns") or []):
            result = agent.chat(user_id, turn["message"])
            payload = result.to_dict()
            # Refresh seed texts after learning turns for later checks if needed
            seeded_texts = _seeded_texts_from_agent(agent, user_id) or seeded_texts
            fails = check_expect(
                turn.get("expect") or {},
                reply=payload["reply"],
                trace=payload["trace"],
                seeded_memory_texts=seeded_texts,
            )
            turn_results.append(
                {
                    "index": i,
                    "message": turn["message"],
                    "passed": not fails,
                    "failures": fails,
                    "reply": payload["reply"],
                    "trace": payload["trace"],
                }
            )
            all_fails.extend([f"turn[{i}]: {f}" for f in fails])
    finally:
        agent.close()

    return {
        "id": case["id"],
        "description": case.get("description", ""),
        "category": case.get("category", "general"),
        "user_id": user_id,
        "passed": not all_fails,
        "failures": all_fails,
        "turns": turn_results,
    }


def run_suite(
    cases: list[dict[str, Any]],
    *,
    backend_name: str,
    category: str | None = None,
    case_id: str | None = None,
) -> dict[str, Any]:
    os.environ["KIVI_SAVE_CHATS"] = "true"
    filtered = cases
    if category:
        filtered = [c for c in filtered if c.get("category") == category]
    if case_id:
        filtered = [c for c in filtered if c["id"] == case_id]
    if not filtered:
        raise SystemExit("No cases matched filters.")

    work = Path(tempfile.mkdtemp(prefix="kivi2_eval_"))
    try:
        results = [run_case(c, backend_name=backend_name, work_dir=work) for c in filtered]
    finally:
        # Windows may keep SQLite handles briefly; ignore cleanup errors.
        import shutil

        shutil.rmtree(work, ignore_errors=True)

    passed = sum(1 for r in results if r["passed"])
    by_cat: dict[str, dict[str, int]] = {}
    for r in results:
        cat = r.get("category") or "general"
        bucket = by_cat.setdefault(cat, {"passed": 0, "failed": 0, "total": 0})
        bucket["total"] += 1
        if r["passed"]:
            bucket["passed"] += 1
        else:
            bucket["failed"] += 1

    report = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "backend": backend_name,
        "total": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "pass_rate": round(passed / len(results), 3) if results else 0.0,
        "by_category": by_cat,
        "results": results,
    }
    return report


def print_summary(report: dict[str, Any]) -> None:
    print(
        f"\nHey Kivi eval — backend={report['backend']}  "
        f"{report['passed']}/{report['total']} passed "
        f"({report['pass_rate'] * 100:.0f}%)\n"
    )
    for cat, stats in sorted(report.get("by_category", {}).items()):
        print(f"  [{cat}] {stats['passed']}/{stats['total']}")
    print()
    for r in report["results"]:
        mark = "PASS" if r["passed"] else "FAIL"
        print(f"  {mark}  {r['id']}")
        for f in r.get("failures") or []:
            print(f"        - {f}")
    print()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Hey Kivi Phase 1 pipeline quality evals")
    parser.add_argument("--cases", type=Path, default=CASES_PATH)
    parser.add_argument("--backend", choices=("stub", "hindsight"), default="stub")
    parser.add_argument("--category", choices=("retrieval", "polish", "learning", "abstain"))
    parser.add_argument("--case", dest="case_id", help="Run a single case id")
    parser.add_argument("--report", type=Path, default=REPORT_PATH)
    parser.add_argument(
        "--integrity",
        action="store_true",
        help="Run integrity contracts (real pipeline imports) instead of quality cases",
    )
    args = parser.parse_args(argv)

    os.environ["KIVI_MEMORY_BACKEND"] = "hindsight"

    if args.integrity:
        from hindsight_pipeline_2.evals.runners.integrity import run_integrity_suite

        work = Path(tempfile.mkdtemp(prefix="kivi2_integrity_"))
        try:
            report = run_integrity_suite(work_dir=work)
        finally:
            import shutil

            shutil.rmtree(work, ignore_errors=True)
        args.report.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        print(
            f"\nHey Kivi integrity — {report['passed']}/{report['total']} passed "
            f"({report['pass_rate'] * 100:.0f}%)\n"
        )
        for r in report["results"]:
            mark = "PASS" if r["passed"] else "FAIL"
            print(f"  {mark}  {r['case_id']}")
            if r.get("error"):
                print(f"        error: {r['error']}")
            if not r["passed"] and r.get("evidence"):
                print(f"        evidence: {json.dumps(r['evidence'], default=str)[:300]}")
        print(f"\nWrote {args.report}")
        return 0 if report["failed"] == 0 else 1

    cases = load_cases(args.cases)
    report = run_suite(
        cases,
        backend_name=args.backend,
        category=args.category,
        case_id=args.case_id,
    )
    args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print_summary(report)
    print(f"Wrote {args.report}")
    return 0 if report["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
