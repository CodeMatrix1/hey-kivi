"""Corpus tests — JSONL import pipeline and ingest reporting.

Tier: corpus (offline stub memory; exercises ``import_corpus`` end-to-end)

Tests:
- test_smoke_jsonl_validates_as_dictation_records — bundled smoke JSONL rows conform to ``DictationRecord`` schema
- test_malformed_json_fails_clearly — malformed JSON lines raise a line-specific validation error
- test_missing_required_fields_fail_validation — rows missing required fields cannot enter ingestion
- test_smoke_import_persists_and_preserves_fields — smoke import persists all rows without mutating source fields
- test_lexical_canonicalization_used_but_asr_preserved — retain uses canonical text; SQLite keeps original ASR
- test_hindsight_retain_invoked_with_provenance — retained dictation includes source id and metadata provenance
- test_user_isolation — CLI ``user_id`` overrides JSONL user_id; data isolated per user
- test_same_dictation_id_allowed_for_different_users — shared corpus ids can import per user
- test_duplicate_id_is_immutable — changed duplicate id is rejected; first version remains stored
- test_reimport_of_unchanged_corpus_skips_hindsight_retain — identical re-import skips append-only retain calls
- test_ingest_jsonl_collects_line_errors — bad lines reported; valid lines in same file still import
- test_fts_finds_asr_only_token_not_in_formatted — FTS indexes ASR tokens absent from formatted text
- test_ingest_report_preserves_asr_and_formatted_distinct — report rows keep both ASR and formatted when they differ
- test_seed_demo_then_reimport_restores_corpus_ingestions — ``seed_demo`` clears markers; re-import restores count
- test_report_file_created_after_first_row — checkpoint report file written after first row with elapsed_ms
- test_partial_report_on_interrupt — KeyboardInterrupt mid-import writes partial report with processed count
- test_rerun_skips_and_reports_correctly — second import skips unchanged rows; ``rerun.latest.json`` updated
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from hindsight_pipeline_2.kivi.config import Settings
from hindsight_pipeline_2.kivi.corpus.import_corpus import (
    DEFAULT_SMOKE,
    ingest_jsonl,
    ingest_record,
    parse_jsonl_line,
)
from hindsight_pipeline_2.kivi.storage.dictation_store import DictationStore
from hindsight_pipeline_2.kivi.instrumentation import sqlite_counts
from hindsight_pipeline_2.kivi.storage.lexical_store import LexicalStore
from hindsight_pipeline_2.kivi.models import DictationRecord, LexicalMapping
from hindsight_pipeline_2.kivi.seed import seed_demo
from hindsight_pipeline_2.kivi.memory.stub_memory import StubMemory


SMOKE_PATH = DEFAULT_SMOKE


@pytest.fixture()
def harness(tmp_path: Path):
    db = tmp_path / "ingest.sqlite3"
    settings = Settings(
        hindsight_base_url="http://localhost:8888",
        hindsight_api_key=None,
        bank_prefix="kivi2ingest",
        memory_backend="hindsight",
        llm_provider="groq",
        db_path=db,
        recall_budget="mid",
    )
    store = DictationStore(db)
    lex = LexicalStore(db)
    memory = StubMemory()
    yield {"settings": settings, "store": store, "lex": lex, "memory": memory}


def test_smoke_jsonl_validates_as_dictation_records():
    """Every bundled smoke row conforms to the DictationRecord schema."""
    assert SMOKE_PATH.is_file()
    lines = [ln for ln in SMOKE_PATH.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert 10 <= len(lines) <= 20
    for i, line in enumerate(lines, start=1):
        rec = parse_jsonl_line(line, line_no=i, user_id=None)
        assert isinstance(rec, DictationRecord)
        assert rec.id and rec.user_id and rec.asr and rec.formatted and rec.created_at
        dumped = rec.model_dump()
        assert set(dumped.keys()) == {"id", "user_id", "asr", "formatted", "created_at"}


def test_malformed_json_fails_clearly():
    """Malformed JSON receives a line-specific validation error."""
    with pytest.raises(ValueError, match="malformed JSON"):
        parse_jsonl_line("{not json", line_no=3, user_id="u")


def test_missing_required_fields_fail_validation():
    """Rows missing DictationRecord fields cannot enter ingestion."""
    with pytest.raises(ValueError, match="invalid DictationRecord"):
        parse_jsonl_line('{"id": "x", "user_id": "u"}', line_no=1, user_id=None)
    with pytest.raises(ValidationError):
        DictationRecord.model_validate({"id": "x", "asr": "hi"})


def test_smoke_import_persists_and_preserves_fields(harness):
    """Import persists every smoke dictation without mutating source fields."""
    report = ingest_jsonl(
        SMOKE_PATH,
        user_id="ingest_user",
        store=harness["store"],
        lexical_store=harness["lex"],
        memory=harness["memory"],
        min_interval_seconds=0,
        write_report=False,
    )
    assert report["ok"] is True
    assert report["failed"] == 0
    assert report["imported"] >= 10
    rows = harness["store"].list_for_user("ingest_user", limit=50)
    assert len(rows) == report["imported"] + report["replaced"]

    rec = harness["store"].get("ingest_user", "d_smoke_03")
    assert rec is not None
    assert "aditya" in rec.asr.lower()
    assert "Aditya" in rec.formatted
    assert rec.created_at == "2026-09-04T17:03:00+00:00"


def test_lexical_canonicalization_used_but_asr_preserved(harness):
    """Retain uses canonical text while SQLite preserves the original transcript."""
    harness["lex"].upsert_mapping(
        "lex_user",
        LexicalMapping(alias="Aditya", canonical="Aaditya", kind="name"),
        source_interaction_id="test",
    )
    record = DictationRecord(
        id="d_lex_1",
        user_id="lex_user",
        asr="talk to aditya about launch",
        formatted="Talk to Aditya about launch.",
        created_at="2026-09-04T17:00:00+00:00",
    )
    detail = ingest_record(
        record,
        store=harness["store"],
        lexical_store=harness["lex"],
        memory=harness["memory"],
    )
    persisted = harness["store"].get("lex_user", "d_lex_1")
    assert persisted is not None
    assert persisted.asr == "talk to aditya about launch"
    assert persisted.formatted == "Talk to Aditya about launch."
    assert "Aaditya" in detail["canonical_formatted"]
    assert "Aditya" not in detail["canonical_formatted"].replace("Aaditya", "")
    assert detail["lexical_applied"]
    assert detail["lexical_applied"][0]["canonical"] == "Aaditya"

    memories = harness["memory"].list_memories("lex_user")
    assert memories
    blob = " ".join(m.get("text", "") for m in memories)
    assert "source_dictation_id=d_lex_1" in blob
    assert "Aaditya" in blob


def test_hindsight_retain_invoked_with_provenance(harness):
    """A retained dictation includes its source ID and metadata provenance."""
    record = DictationRecord(
        id="d_ret_1",
        user_id="ret_user",
        asr="working on payment reconciliation",
        formatted="Working on payment reconciliation.",
        created_at="2026-09-02T14:00:00+00:00",
    )
    detail = ingest_record(
        record,
        store=harness["store"],
        lexical_store=harness["lex"],
        memory=harness["memory"],
    )
    assert detail["retain"]["ok"] is True
    assert detail["retain"]["memory_id"] == "dict_d_ret_1"
    memories = harness["memory"].list_memories("ret_user")
    assert any(m.get("id") == "dict_d_ret_1" for m in memories)
    assert any("source_dictation_id=d_ret_1" in (m.get("text") or "") for m in memories)
    meta = next(m for m in memories if m.get("id") == "dict_d_ret_1")["metadata"]
    assert meta.get("dictation_id") == "d_ret_1"


def test_user_isolation(harness):
    """The requested import user overrides corpus input and isolates stored data."""
    path = harness["settings"].db_path.parent / "mini.jsonl"
    path.write_text(
        json.dumps(
            {
                "id": "d_iso_1",
                "user_id": "ignored",
                "asr": "private token alpha",
                "formatted": "Private token alpha.",
                "created_at": "2026-09-01T00:00:00+00:00",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    ingest_jsonl(
        path,
        user_id="user_a",
        store=harness["store"],
        lexical_store=harness["lex"],
        memory=harness["memory"],
        min_interval_seconds=0,
        write_report=False,
    )
    assert harness["store"].get("user_a", "d_iso_1") is not None
    assert harness["store"].get("user_b", "d_iso_1") is None
    assert harness["memory"].list_memories("user_a")
    assert harness["memory"].list_memories("user_b") == []


def test_same_dictation_id_allowed_for_different_users(harness):
    """Baseline and Path B users can both own the same corpus dictation id."""
    shared_id = "hist_001"
    baseline = DictationRecord(
        id=shared_id,
        user_id="golden_goose_eval_user",
        asr="baseline row",
        formatted="Baseline row.",
        created_at="2026-09-01T00:00:00+00:00",
    )
    repro = DictationRecord(
        id=shared_id,
        user_id="corpus_repro_user",
        asr="repro row",
        formatted="Repro row.",
        created_at="2026-09-01T00:00:00+00:00",
    )
    first = ingest_record(
        baseline,
        store=harness["store"],
        lexical_store=harness["lex"],
        memory=harness["memory"],
    )
    second = ingest_record(
        repro,
        store=harness["store"],
        lexical_store=harness["lex"],
        memory=harness["memory"],
    )
    assert first["status"] == "imported"
    assert second["status"] == "imported"
    assert harness["store"].get("golden_goose_eval_user", shared_id).formatted == "Baseline row."
    assert harness["store"].get("corpus_repro_user", shared_id).formatted == "Repro row."


def test_duplicate_id_is_immutable(harness):
    """A changed duplicate dictation ID is rejected rather than silently updated."""
    record = DictationRecord(
        id="d_dup_1",
        user_id="dup_user",
        asr="first version",
        formatted="First version.",
        created_at="2026-09-01T00:00:00+00:00",
    )
    first = ingest_record(
        record,
        store=harness["store"],
        lexical_store=harness["lex"],
        memory=harness["memory"],
    )
    assert first["status"] == "imported"
    updated = DictationRecord(
        id="d_dup_1",
        user_id="dup_user",
        asr="second version",
        formatted="Second version.",
        created_at="2026-09-01T01:00:00+00:00",
    )
    with pytest.raises(ValueError, match="immutable"):
        ingest_record(
            updated,
            store=harness["store"],
            lexical_store=harness["lex"],
            memory=harness["memory"],
        )
    persisted = harness["store"].get("dup_user", "d_dup_1")
    assert persisted is not None
    assert persisted.asr == "first version"
    assert persisted.formatted == "First version."


def test_reimport_of_unchanged_corpus_skips_hindsight_retain(harness):
    """Reimporting identical content skips the append-only Hindsight retain call."""
    first = ingest_jsonl(
        SMOKE_PATH,
        user_id="repeat_user",
        store=harness["store"],
        lexical_store=harness["lex"],
        memory=harness["memory"],
        min_interval_seconds=0,
        write_report=False,
    )
    retained_count = len(harness["memory"].list_memories("repeat_user"))

    second = ingest_jsonl(
        SMOKE_PATH,
        user_id="repeat_user",
        store=harness["store"],
        lexical_store=harness["lex"],
        memory=harness["memory"],
        min_interval_seconds=0,
        write_report=False,
    )

    assert first["imported"] >= 10
    assert second["skipped"] == first["imported"]
    assert second["imported"] == 0
    assert second["replaced"] == 0
    assert len(harness["memory"].list_memories("repeat_user")) == retained_count


def test_ingest_jsonl_collects_line_errors(harness, tmp_path: Path):
    """Bad lines are reported while valid lines in the same corpus still import."""
    bad = tmp_path / "bad.jsonl"
    bad.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "id": "ok1",
                        "user_id": "x",
                        "asr": "a",
                        "formatted": "A.",
                        "created_at": "2026-09-01T00:00:00+00:00",
                    }
                ),
                "{bad",
                json.dumps({"id": "missing_fields"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    report = ingest_jsonl(
        bad,
        user_id="err_user",
        store=harness["store"],
        lexical_store=harness["lex"],
        memory=harness["memory"],
        min_interval_seconds=0,
        write_report=False,
    )
    assert report["ok"] is False
    assert report["imported"] == 1
    assert report["failed"] == 2
    assert len(report["errors"]) == 2


def test_fts_finds_asr_only_token_not_in_formatted(harness):
    """FTS indexes ASR text even when the token is absent from formatted."""
    record = DictationRecord(
        id="d_asr_only",
        user_id="fts_user",
        asr="unique_asr_token_xyzabc mentioned in transcript",
        formatted="Polished summary without the token.",
        created_at="2026-09-04T10:00:00+00:00",
    )
    harness["store"].add_dictation(record)
    hits = harness["store"].find("fts_user", text_query="xyzabc")
    assert [hit["id"] for hit in hits] == ["d_asr_only"]


def test_ingest_report_preserves_asr_and_formatted_distinct(harness, tmp_path: Path):
    """Ingest report rows preserve both ASR and formatted when they differ."""
    report_dir = tmp_path / "reports"
    lines = [ln for ln in SMOKE_PATH.read_text(encoding="utf-8").splitlines() if ln.strip()][:1]
    corpus = tmp_path / "one.jsonl"
    corpus.write_text(lines[0] + "\n", encoding="utf-8")

    report = ingest_jsonl(
        corpus,
        user_id="report_user",
        store=harness["store"],
        lexical_store=harness["lex"],
        memory=harness["memory"],
        min_interval_seconds=0,
        report_dir=report_dir,
    )

    row = report["results"][0]
    assert row["asr"] != row["formatted"]
    assert row["asr"] and row["formatted"]
    assert Path(report["report_path"]).is_file()


def test_seed_demo_then_reimport_restores_corpus_ingestions(harness):
    """seed_demo clears corpus_ingestions; re-import restores the marker count."""
    user = "lifecycle_user"
    first = ingest_jsonl(
        SMOKE_PATH,
        user_id=user,
        store=harness["store"],
        lexical_store=harness["lex"],
        memory=harness["memory"],
        min_interval_seconds=0,
        write_report=False,
    )
    before_clear = sqlite_counts(harness["settings"].db_path, user)["corpus_ingestions"]
    assert before_clear == first["imported"]

    seed_demo(user, settings=harness["settings"])
    after_seed = sqlite_counts(harness["settings"].db_path, user)["corpus_ingestions"]
    assert after_seed == 0

    second = ingest_jsonl(
        SMOKE_PATH,
        user_id=user,
        store=harness["store"],
        lexical_store=harness["lex"],
        memory=harness["memory"],
        min_interval_seconds=0,
        write_report=False,
    )
    after_reimport = sqlite_counts(harness["settings"].db_path, user)["corpus_ingestions"]
    assert after_reimport == before_clear
    assert second["imported"] == first["imported"]


def test_report_file_created_after_first_row(tmp_path: Path, harness):
    report_dir = tmp_path / "reports"
    lines = [ln for ln in SMOKE_PATH.read_text(encoding="utf-8").splitlines() if ln.strip()][:1]
    corpus = tmp_path / "one.jsonl"
    corpus.write_text(lines[0] + "\n", encoding="utf-8")

    report = ingest_jsonl(
        corpus,
        user_id="cp_user",
        store=harness["store"],
        lexical_store=harness["lex"],
        memory=harness["memory"],
        min_interval_seconds=0,
        report_dir=report_dir,
    )

    assert report["status"] == "complete"
    assert report["imported"] == 1
    assert report["results"][0].get("elapsed_ms") is not None
    assert report.get("report_path")
    assert Path(report["report_path"]).is_file()
    payload = json.loads(Path(report["report_path"]).read_text(encoding="utf-8"))
    assert payload["status"] == "complete"
    assert len(payload["results"]) == 1


def test_partial_report_on_interrupt(tmp_path: Path, harness):
    report_dir = tmp_path / "reports"
    lines = [ln for ln in SMOKE_PATH.read_text(encoding="utf-8").splitlines() if ln.strip()][:5]
    corpus = tmp_path / "five.jsonl"
    corpus.write_text("\n".join(lines) + "\n", encoding="utf-8")
    calls = {"n": 0}

    def _ingest(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] >= 3:
            raise KeyboardInterrupt()
        return ingest_record(*args, **kwargs)

    with patch("hindsight_pipeline_2.kivi.corpus.import_corpus.ingest_record", side_effect=_ingest):
        with pytest.raises(KeyboardInterrupt):
            ingest_jsonl(
                corpus,
                user_id="partial_user",
                store=harness["store"],
                lexical_store=harness["lex"],
                memory=harness["memory"],
                min_interval_seconds=0,
                report_dir=report_dir,
            )

    reports = list(report_dir.glob("five_*.json"))
    assert reports
    payload = json.loads(reports[0].read_text(encoding="utf-8"))
    assert payload["status"] == "partial"
    assert payload["total_processed"] == 2
    assert len(payload["results"]) == 2
    assert payload["ok"] is False


def test_rerun_skips_and_reports_correctly(tmp_path: Path, harness):
    report_dir = tmp_path / "reports"
    lines = [ln for ln in SMOKE_PATH.read_text(encoding="utf-8").splitlines() if ln.strip()][:5]
    corpus = tmp_path / "rerun.jsonl"
    corpus.write_text("\n".join(lines) + "\n", encoding="utf-8")

    first = ingest_jsonl(
        corpus,
        user_id="rerun_user",
        store=harness["store"],
        lexical_store=harness["lex"],
        memory=harness["memory"],
        min_interval_seconds=0,
        report_dir=report_dir,
    )
    assert first["imported"] == 5

    second = ingest_jsonl(
        corpus,
        user_id="rerun_user",
        store=harness["store"],
        lexical_store=harness["lex"],
        memory=harness["memory"],
        min_interval_seconds=0,
        report_dir=report_dir,
    )
    assert second["skipped"] == 5
    assert second["imported"] == 0
    assert second["status"] == "complete"
    assert second["retain_call_count"] == 0
    assert (report_dir / "rerun.latest.json").is_file()
