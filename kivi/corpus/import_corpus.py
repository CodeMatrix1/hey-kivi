"""Import JSONL dictations into SQLite + Hindsight (shared by CLI and API).

Path:
  JSONL → DictationRecord → DictationStore → lexical resolve → memory.retain

Original ASR/formatted in SQLite are never overwritten by lexical normalization.
Canonicalized *formatted* text is what is sent to Hindsight retain, with the
dictation id embedded for provenance.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from hindsight_pipeline_2.kivi.config import Settings
from hindsight_pipeline_2.kivi.corpus.lexical_from_corpus import mapping_from_corpus_record
from hindsight_pipeline_2.kivi.corpus.text_cleanup import strip_corpus_metadata_noise
from hindsight_pipeline_2.kivi.storage.dictation_store import DictationStore
from hindsight_pipeline_2.kivi.memory.hindsight_adapter import get_memory_backend
from hindsight_pipeline_2.kivi.instrumentation import MetricsTimer, sqlite_counts
from hindsight_pipeline_2.kivi.storage.lexical import resolve_lexical_mappings
from hindsight_pipeline_2.kivi.storage.lexical_store import LexicalStore
from hindsight_pipeline_2.kivi.models import DictationRecord

from hindsight_pipeline_2.paths import ARTIFACTS_REPORTS_DIR, DEFAULT_SMOKE

REPORTS_DIR = ARTIFACTS_REPORTS_DIR


def _retain_content(record: DictationRecord, canonical_formatted: str) -> str:
    """Attach dictation provenance; body is lexical-canonicalized formatted text."""
    header = (
        f"[source_dictation_id={record.id} "
        f"created_at={record.created_at} user_id={record.user_id}]"
    )
    return f"{header}\n{canonical_formatted}"


def _provider_retry_seconds(message: str) -> float | None:
    """Extract Groq retry guidance such as ``6m6.768s`` or ``19.71s``."""
    match = re.search(
        r"try again in\s+(?:(?P<minutes>[0-9]+)m)?"
        r"(?P<seconds>[0-9]+(?:\.[0-9]+)?)s",
        message.lower(),
    )
    if not match:
        return None
    return int(match.group("minutes") or 0) * 60 + float(match.group("seconds"))


def _retain_with_retries(
    memory: Any,
    user_id: str,
    content: str,
    *,
    metadata: dict[str, Any],
    attempts: int = 4,
) -> dict[str, Any]:
    """Call retain with backoff that respects provider rate-limit guidance."""
    last_exc: Exception | None = None
    for attempt in range(attempts):
        try:
            return memory.retain(user_id, content, metadata=metadata)
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            msg = str(exc).lower()
            transient = (
                "rate_limit" in msg
                or "429" in msg
                or "tpm" in msg
                or "timeout context manager" in msg
            )
            if not transient or attempt >= attempts - 1:
                raise
            retry_seconds = _provider_retry_seconds(msg)
            wait_seconds = retry_seconds + 1.0 if retry_seconds is not None else 5.0 * (attempt + 1)
            time.sleep(wait_seconds)
    assert last_exc is not None
    raise last_exc


def _normalize_corpus_record(record: DictationRecord) -> DictationRecord:
    """Strip synthetic scaffolding from formatted text before SQLite retain."""
    clean_formatted = strip_corpus_metadata_noise(record.formatted)
    if clean_formatted == record.formatted:
        return record
    return record.model_copy(update={"formatted": clean_formatted})


def ingest_record(
    record: DictationRecord,
    *,
    store: DictationStore,
    lexical_store: LexicalStore,
    memory: Any,
) -> dict[str, Any]:
    """Persist one dictation and retain it once per distinct canonical payload."""
    row_timer = MetricsTimer()
    record = _normalize_corpus_record(record)
    existing = store.get(record.user_id, record.id)
    corpus_mapping = mapping_from_corpus_record(record)
    if corpus_mapping is not None:
        lexical_store.upsert_mapping(
            record.user_id, corpus_mapping, source_interaction_id=record.id
        )
    canonical, applied = resolve_lexical_mappings(
        record.user_id, record.formatted, lexical_store
    )
    content = _retain_content(record, canonical)
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

    # The SQLite marker lives on the persistent kivi2_sqlite volume.  It makes
    # repeated imports safe even though Hindsight's retain API is append-only.
    prior_ingestion = store.ingestion_for(record.user_id, record.id)
    if existing is None:
        store.add_dictation(record)
    elif existing != record:
        raise ValueError(f"dictation {record.id!r} already exists and is immutable")
    if prior_ingestion and prior_ingestion["content_hash"] == content_hash:
        return {
            "id": record.id,
            "user_id": record.user_id,
            "status": "skipped",
            "asr": record.asr,
            "formatted": record.formatted,
            "created_at": record.created_at,
            "canonical_formatted": canonical,
            "lexical_applied": [
                {"alias": m.alias, "canonical": m.canonical, "kind": m.kind} for m in applied
            ],
            "retain": {
                "ok": True,
                "skipped": True,
                "bank_id": None,
                "memory_id": prior_ingestion.get("memory_id"),
            },
            "elapsed_ms": round(row_timer.elapsed_ms(), 2),
        }

    retain_result = _retain_with_retries(
        memory,
        record.user_id,
        content,
        metadata={
            "dictation_id": record.id,
            "created_at": record.created_at,
            "id": f"dict_{record.id}",
        },
    )
    memory_id = retain_result.get("id") or (retain_result.get("metadata") or {}).get("id")
    store.mark_ingested(
        record.user_id,
        record.id,
        content_hash=content_hash,
        memory_id=memory_id,
    )
    return {
        "id": record.id,
        "user_id": record.user_id,
        "status": "replaced" if existing is not None else "imported",
        "asr": record.asr,
        "formatted": record.formatted,
        "created_at": record.created_at,
        "canonical_formatted": canonical,
        "lexical_applied": [
            {"alias": m.alias, "canonical": m.canonical, "kind": m.kind} for m in applied
        ],
        "retain": {
            "ok": True,
            "bank_id": retain_result.get("bank_id"),
            "memory_id": memory_id,
        },
        "elapsed_ms": round(row_timer.elapsed_ms(), 2),
    }


def parse_jsonl_line(line: str, *, line_no: int, user_id: str | None) -> DictationRecord:
    """Parse one JSONL line into a validated DictationRecord."""
    text = line.strip()
    if not text:
        raise ValueError(f"line {line_no}: empty line")
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"line {line_no}: malformed JSON ({exc})") from exc
    if not isinstance(raw, dict):
        raise ValueError(f"line {line_no}: expected a JSON object")
    if user_id:
        raw = {**raw, "user_id": user_id}
    try:
        return DictationRecord.model_validate(raw)
    except ValidationError as exc:
        raise ValueError(f"line {line_no}: invalid DictationRecord ({exc})") from exc


def allocate_report_path(
    corpus_path: Path,
    started_at: str,
    *,
    report_dir: Path | None = None,
) -> Path:
    """Stable report path for one ingest run (stem + started_at)."""
    report_dir = report_dir or REPORTS_DIR
    report_dir.mkdir(parents=True, exist_ok=True)
    stamp = started_at.replace(":", "-")
    return report_dir / f"{corpus_path.stem}_{stamp}.json"


def checkpoint_report(report: dict[str, Any], report_path: Path) -> None:
    """Atomically write the in-progress or final ingest report."""
    report["report_path"] = str(report_path.resolve())
    tmp = report_path.with_suffix(f"{report_path.suffix}.tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
    tmp.replace(report_path)


def write_ingest_report(
    report: dict[str, Any],
    *,
    report_dir: Path | None = None,
    report_path: Path | None = None,
) -> Path:
    """Write ingest report JSON (uses pre-allocated path when provided)."""
    if report_path is None:
        corpus = Path(str(report.get("path") or report.get("corpus") or "ingest"))
        started_at = str(
            report.get("started_at") or report.get("generated_at") or report.get("finished_at") or ""
        )
        report_path = allocate_report_path(
            corpus,
            started_at or "ingest",
            report_dir=report_dir,
        )
    checkpoint_report(report, report_path)
    return report_path


def _estimate_retain_cost_usd(retain_call_count: int) -> float:
    """Rough placeholder; document exact pricing in README."""
    per_call = float(os.getenv("KIVI_ESTIMATED_RETAIN_COST_USD", "0"))
    return round(retain_call_count * per_call, 4)


def _build_report(
    *,
    path: Path,
    user_id: str,
    store: DictationStore,
    memory: Any,
    started_at: str,
    db_before: dict[str, int],
    results: list[dict[str, Any]],
    errors: list[dict[str, Any]],
    imported: int,
    replaced: int,
    skipped: int,
    failed: int,
    timer: MetricsTimer,
    status: str,
) -> dict[str, Any]:
    finished_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    retain_call_count = sum(1 for r in results if r.get("status") in {"imported", "replaced"})
    return {
        "ok": failed == 0 and status == "complete",
        "status": status,
        "path": str(path.resolve()),
        "user_id": user_id,
        "imported": imported,
        "replaced": replaced,
        "skipped": skipped,
        "failed": failed,
        "total_processed": imported + replaced + skipped + failed,
        "results": results,
        "errors": errors,
        "db_path": str(store.db_path),
        "memory_backend": getattr(memory, "backend_name", type(memory).__name__),
        "started_at": started_at,
        "finished_at": finished_at,
        "elapsed_ms": round(timer.elapsed_ms(), 2),
        "db_before": db_before,
        "db_after": sqlite_counts(store.db_path, user_id),
        "retain_call_count": retain_call_count,
        "cost_usd": _estimate_retain_cost_usd(retain_call_count),
    }


def ingest_jsonl(
    path: Path | str,
    *,
    user_id: str,
    store: DictationStore,
    lexical_store: LexicalStore,
    memory: Any,
    progress: bool = False,
    min_interval_seconds: float | None = None,
    write_report: bool = True,
    report_dir: Path | None = None,
) -> dict[str, Any]:
    """Import all JSONL rows for ``user_id`` through the shared ingestion path."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"corpus file not found: {path}")

    timer = MetricsTimer()
    started_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    db_before = sqlite_counts(store.db_path, user_id)

    results: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    imported = 0
    replaced = 0
    skipped = 0
    failed = 0
    status = "in_progress"
    report_path: Path | None = None
    if min_interval_seconds is None:
        min_interval_seconds = float(os.getenv("HINDSIGHT_RETAIN_MIN_INTERVAL_SECONDS", "30"))
    if min_interval_seconds < 0:
        raise ValueError("min_interval_seconds must be non-negative")

    def _checkpoint() -> dict[str, Any]:
        return _build_report(
            path=path,
            user_id=user_id,
            store=store,
            memory=memory,
            started_at=started_at,
            db_before=db_before,
            results=results,
            errors=errors,
            imported=imported,
            replaced=replaced,
            skipped=skipped,
            failed=failed,
            timer=timer,
            status=status,
        )

    if write_report:
        report_path = allocate_report_path(path, started_at, report_dir=report_dir)
        checkpoint_report(_checkpoint(), report_path)

    try:
        with path.open(encoding="utf-8") as handle:
            for line_no, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                if progress:
                    print(
                        f"[progress] line={line_no} status=processing",
                        flush=True,
                    )
                try:
                    record = parse_jsonl_line(line, line_no=line_no, user_id=user_id)
                    detail = ingest_record(
                        record,
                        store=store,
                        lexical_store=lexical_store,
                        memory=memory,
                    )
                    results.append(detail)
                    if detail["status"] == "replaced":
                        replaced += 1
                    elif detail["status"] == "skipped":
                        skipped += 1
                    else:
                        imported += 1
                    if (
                        getattr(memory, "backend_name", "") == "hindsight"
                        and detail["status"] != "skipped"
                    ):
                        time.sleep(min_interval_seconds)
                except Exception as exc:  # noqa: BLE001 — collect per-line failures
                    failed += 1
                    errors.append({"line": line_no, "error": str(exc)})
                    if getattr(memory, "backend_name", "") == "hindsight":
                        time.sleep(min_interval_seconds)
                    if progress:
                        print(
                            f"[progress] line={line_no} status=failed "
                            f"processed={imported + replaced + skipped + failed} "
                            f"imported={imported} replaced={replaced} "
                            f"skipped={skipped} failed={failed} error={exc}",
                            flush=True,
                        )
                else:
                    if progress:
                        print(
                            f"[progress] line={line_no} id={detail['id']} "
                            f"status={detail['status']} "
                            f"processed={imported + replaced + skipped} "
                            f"imported={imported} replaced={replaced} skipped={skipped} "
                            f"failed={failed}",
                            flush=True,
                        )
                if write_report and report_path is not None:
                    checkpoint_report(_checkpoint(), report_path)

        status = "complete"
    except KeyboardInterrupt:
        status = "partial"
        raise
    except Exception:
        status = "partial"
        raise
    finally:
        if status == "in_progress":
            status = "partial"
        report = _checkpoint()
        if write_report and report_path is not None:
            checkpoint_report(report, report_path)
            if status == "complete" and report.get("ok"):
                latest = (report_dir or REPORTS_DIR) / f"{path.stem}.latest.json"
                latest.write_text(
                    json.dumps(report, indent=2),
                    encoding="utf-8",
                )

    return report


def build_default_services(
    settings: Settings | None = None,
) -> tuple[Settings, DictationStore, LexicalStore, Any]:
    cfg = settings or Settings.from_env()
    store = DictationStore(cfg.db_path)
    lexical_store = LexicalStore(cfg.db_path)
    memory = get_memory_backend(cfg)
    return cfg, store, lexical_store, memory


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Import DictationRecord JSONL → SQLite → lexical → Hindsight retain"
    )
    parser.add_argument(
        "--path",
        type=Path,
        default=DEFAULT_SMOKE,
        help=f"JSONL path (default: {DEFAULT_SMOKE})",
    )
    parser.add_argument(
        "--user-id",
        required=True,
        help="Target user_id (overrides per-line user_id; enforces isolation)",
    )
    parser.add_argument(
        "--progress",
        action="store_true",
        help="Print a flushed progress line after each processed row",
    )
    parser.add_argument(
        "--min-interval-seconds",
        type=float,
        default=None,
        help="Minimum delay after each real Hindsight row (default: env or 30)",
    )
    args = parser.parse_args(argv)

    _, store, lexical_store, memory = build_default_services()
    try:
        report = ingest_jsonl(
            args.path,
            user_id=args.user_id.strip(),
            store=store,
            lexical_store=lexical_store,
            memory=memory,
            progress=args.progress,
            min_interval_seconds=args.min_interval_seconds,
        )
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    finally:
        close = getattr(memory, "close", None)
        if callable(close):
            close()

    print(json.dumps({k: report[k] for k in (
        "ok", "status", "path", "user_id", "imported", "replaced", "skipped", "failed",
        "total_processed", "db_path", "memory_backend", "retain_call_count",
        "elapsed_ms", "report_path", "errors",
    )}, indent=2))
    # Compact per-row summary
    for row in report["results"]:
        lex = ",".join(f"{x['alias']}→{x['canonical']}" for x in row["lexical_applied"]) or "-"
        print(
            f"  [{row['status']}] {row['id']} "
            f"retain={row['retain'].get('memory_id') or 'ok'} lexical={lex}"
        )
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
