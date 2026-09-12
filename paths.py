"""Central filesystem paths for the Hey Kivi package."""

from __future__ import annotations

from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
KIVI_DIR = PACKAGE_DIR / "kivi"

DOCS_DIR = PACKAGE_DIR / "docs"
OPS_DIR = PACKAGE_DIR / "ops"
OPS_DOCKER_DIR = OPS_DIR / "docker"
OPS_SCRIPTS_DIR = OPS_DIR / "scripts"
OPS_BASELINE_DIR = OPS_DIR / "baseline-volumes"

DATA_DIR = PACKAGE_DIR / "data"
DATA_CORPUS_DIR = DATA_DIR / "corpus"
DATA_FIXTURES_DIR = DATA_DIR / "fixtures"

ARTIFACTS_DIR = PACKAGE_DIR / "artifacts"
ARTIFACTS_REPORTS_DIR = ARTIFACTS_DIR / "reports"
ARTIFACTS_EVALS_DIR = ARTIFACTS_DIR / "evals"
ARTIFACTS_RUNTIME_DIR = ARTIFACTS_DIR / "runtime"

WEB_DIR = PACKAGE_DIR / "web"
WEB_DIST_DIR = WEB_DIR / "dist"
WEB_ASSETS_DIR = WEB_DIR / "assets"

EVALS_DIR = PACKAGE_DIR / "evals"

DEFAULT_DB_PATH = ARTIFACTS_RUNTIME_DIR / "kivi.sqlite3"
DEFAULT_CORPUS = DATA_CORPUS_DIR / "kivi_corpus_500_history.jsonl"
DEFAULT_SMOKE = DATA_CORPUS_DIR / "smoke.jsonl"
