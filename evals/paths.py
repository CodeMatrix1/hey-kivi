"""Central paths for eval case files and generated artifacts."""

from __future__ import annotations

from pathlib import Path

from hindsight_pipeline_2.paths import (
    ARTIFACTS_EVALS_DIR,
    ARTIFACTS_REPORTS_DIR,
    DATA_CORPUS_DIR,
    DEFAULT_CORPUS,
    EVALS_DIR,
    PACKAGE_DIR,
    WEB_ASSETS_DIR,
)

CASES_DIR = EVALS_DIR / "cases"
ARTIFACTS_DIR = ARTIFACTS_EVALS_DIR

DEMO_CASES_PATH = CASES_DIR / "demo_cases.json"
QUERY_CASES_PATH = CASES_DIR / "query_cases.json"
INTEGRITY_CASES_PATH = CASES_DIR / "integrity.json"
LAST_RUN_PATH = ARTIFACTS_EVALS_DIR / "last_run.json"
CORPUS_REPORTS_DIR = ARTIFACTS_REPORTS_DIR
QUERY_CASES_STATIC = WEB_ASSETS_DIR / "query_cases.json"
