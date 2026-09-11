"""Scenario tests — JSON case runners (stub-backed full pipeline).

Tier: scenario (runs real ``runners/*`` code against case JSON; not live Docker)

Tests:
- test_pipeline_quality_suite_stub — runs ``demo_cases.json`` quality suite via ``runners.quality`` (stub memory)
- test_corpus_runner_full_query_cases_stub — imports 500-corpus + runs all ``query_cases.json`` via ``runners.corpus``
- test_integrity_suite_passes — runs every case in ``integrity.json`` via ``runners.integrity`` (retain/recall/find wiring)

For Docker + Hindsight integration, run the CLIs with ``--backend hindsight`` (see ``integration/README.md``).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hindsight_pipeline_2.evals.paths import DEMO_CASES_PATH, INTEGRITY_CASES_PATH, QUERY_CASES_PATH
from hindsight_pipeline_2.evals.paths import DEFAULT_CORPUS
from hindsight_pipeline_2.evals.runners.corpus import run_corpus_eval
from hindsight_pipeline_2.evals.runners.expect import load_cases
from hindsight_pipeline_2.evals.runners.integrity import load_cases as load_integrity_cases
from hindsight_pipeline_2.evals.runners.integrity import make_harness, run_case
from hindsight_pipeline_2.evals.runners.quality import run_suite


def test_pipeline_quality_suite_stub():
    """Run the case-driven conversational quality suite using stub memory."""
    report = run_suite(load_cases(DEMO_CASES_PATH), backend_name="stub")
    assert report["failed"] == 0, report


def test_corpus_runner_full_query_cases_stub(tmp_path: Path):
    """Full query_cases.json against 500-corpus import must pass with stub backend."""
    cases = load_cases(QUERY_CASES_PATH)
    report = run_corpus_eval(
        corpus=DEFAULT_CORPUS,
        user_id="runner_full_user",
        cases_path=QUERY_CASES_PATH,
        report_dir=tmp_path / "reports",
        backend="stub",
    )
    assert report["ingest"]["ok"] is True
    assert report["chat_cases"]["failed"] == 0, report["chat_cases"]
    assert report["chat_cases"]["total"] == len(cases)
    assert report["chat_cases"]["passed"] == len(cases)
    for result in report["chat_cases"]["results"]:
        assert "trace" in result
        assert "decision" in result["trace"]


@pytest.fixture()
def integrity_work_dir(tmp_path: Path) -> Path:
    return tmp_path


def test_integrity_suite_passes(integrity_work_dir: Path):
    harness = make_harness(integrity_work_dir)
    try:
        for case in load_integrity_cases():
            outcome = run_case(harness, case)
            assert outcome["passed"], outcome
    finally:
        harness["agent"].close()
