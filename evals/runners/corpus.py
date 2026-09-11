"""Full-pipeline corpus evaluation: ingest + scripted chat probes."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hindsight_pipeline_2.kivi.agent import HeyKiviAgent
from hindsight_pipeline_2.kivi.config import Settings
from hindsight_pipeline_2.kivi.corpus.import_corpus import ingest_jsonl, write_ingest_report
from hindsight_pipeline_2.kivi.storage.dictation_store import DictationStore
from hindsight_pipeline_2.evals.paths import CORPUS_REPORTS_DIR, DEFAULT_CORPUS, QUERY_CASES_PATH
from hindsight_pipeline_2.evals.runners.expect import check_expect, load_cases
from hindsight_pipeline_2.kivi.memory.hindsight_adapter import get_memory_backend
from hindsight_pipeline_2.kivi.instrumentation import MetricsTimer, count_llm_calls, sqlite_counts
from hindsight_pipeline_2.kivi.lexical.lexical_extract import scripted_lexical_llm
from hindsight_pipeline_2.kivi.storage.lexical_store import LexicalStore
from hindsight_pipeline_2.kivi.models import DictationRecord, LexicalMapping
from hindsight_pipeline_2.kivi.memory.stub_memory import StubMemory

CASES_PATH = QUERY_CASES_PATH
REPORT_DIR = CORPUS_REPORTS_DIR


def run_chat_cases(
    agent: HeyKiviAgent,
    user_id: str,
    cases: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    outcomes: list[dict[str, Any]] = []
    for case in cases:
        for msg in case.get("setup_messages") or []:
            agent.chat(user_id, msg)
        for raw in case.get("seed_dictations") or []:
            payload = dict(raw)
            payload.setdefault("user_id", user_id)
            agent.store.add_dictation(DictationRecord(**payload))
        for raw in case.get("seed_lexical") or []:
            agent.lexical_store.upsert_mapping(
                user_id,
                LexicalMapping(**raw),
                source_interaction_id="corpus_runner",
            )
        timer = MetricsTimer()
        result = agent.chat(user_id, case["message"])
        payload = result.to_dict()
        seeded = [str(m.get("text") or "") for m in agent.memory.list_memories(user_id)]
        fails = check_expect(
            case.get("expect") or {},
            reply=payload["reply"],
            trace=payload["trace"],
            seeded_memory_texts=seeded,
        )
        outcomes.append(
            {
                "id": case["id"],
                "message": case["message"],
                "passed": not fails,
                "failures": fails,
                "elapsed_ms": round(timer.elapsed_ms(), 2),
                "llm_call_count": count_llm_calls(payload["trace"]),
                "reply": payload["reply"],
                "trace": payload["trace"],
            }
        )
    return outcomes


def run_corpus_eval(
    *,
    corpus: Path,
    user_id: str,
    cases_path: Path,
    report_dir: Path,
    backend: str = "stub",
    limit: int | None = None,
) -> dict[str, Any]:
    os.environ["KIVI_SAVE_CHATS"] = "true"
    work = Path(tempfile.mkdtemp(prefix="kivi2_corpus_eval_"))
    db_path = work / "eval.sqlite3"
    settings = Settings(
        hindsight_base_url="http://localhost:8888",
        hindsight_api_key=None,
        bank_prefix=f"kivi2corpus_{user_id}"[:48],
        memory_backend="hindsight",
        llm_provider="groq",
        db_path=db_path,
        recall_budget="mid",
    )
    store = DictationStore(db_path)
    lexical_store = LexicalStore(db_path)
    if backend == "stub":
        memory = StubMemory()
    else:
        memory = get_memory_backend(settings)
        try:
            memory.reset(user_id)
        except Exception:  # noqa: BLE001
            pass

    ingest_path = corpus
    if limit is not None:
        lines = [ln for ln in corpus.read_text(encoding="utf-8").splitlines() if ln.strip()][:limit]
        ingest_path = work / "limited.jsonl"
        ingest_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    ingest_report = ingest_jsonl(
        ingest_path,
        user_id=user_id,
        store=store,
        lexical_store=lexical_store,
        memory=memory,
        min_interval_seconds=0 if backend == "stub" else None,
        write_report=False,
    )
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
    try:
        chat_results = run_chat_cases(agent, user_id, load_cases(cases_path))
    finally:
        agent.close()
        close = getattr(memory, "close", None)
        if callable(close):
            close()

    passed = sum(1 for r in chat_results if r["passed"])
    report = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "backend": backend,
        "corpus": str(corpus.resolve()),
        "user_id": user_id,
        "ingest": ingest_report,
        "chat_cases": {
            "total": len(chat_results),
            "passed": passed,
            "failed": len(chat_results) - passed,
            "results": chat_results,
        },
        "db_counts": sqlite_counts(db_path, user_id),
        "cost_usd": 0.0,
    }
    write_ingest_report(report, report_dir=report_dir)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run corpus ingest + chat probe evaluation")
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--user-id", default="corpus_eval_user")
    parser.add_argument("--cases", type=Path, default=CASES_PATH)
    parser.add_argument("--report-dir", type=Path, default=REPORT_DIR)
    parser.add_argument("--backend", choices=("stub", "hindsight"), default="stub")
    parser.add_argument("--limit", type=int, default=None, help="Import only first N JSONL rows")
    args = parser.parse_args(argv)
    report = run_corpus_eval(
        corpus=args.corpus,
        user_id=args.user_id.strip(),
        cases_path=args.cases,
        report_dir=args.report_dir,
        backend=args.backend,
        limit=args.limit,
    )
    print(json.dumps(
        {
            "report_path": report.get("report_path"),
            "ingest_ok": report["ingest"]["ok"],
            "chat_passed": report["chat_cases"]["passed"],
            "chat_total": report["chat_cases"]["total"],
        },
        indent=2,
    ))
    return 0 if report["chat_cases"]["failed"] == 0 and report["ingest"]["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
