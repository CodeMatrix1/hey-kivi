"""CLI entry: corpus ingest + query-case probes. Implementation in evals.runners.corpus."""

from hindsight_pipeline_2.evals.paths import CORPUS_REPORTS_DIR, DEFAULT_CORPUS, QUERY_CASES_PATH
from hindsight_pipeline_2.evals.runners.corpus import (
    CASES_PATH,
    REPORT_DIR,
    main,
    run_chat_cases,
    run_corpus_eval,
)
from hindsight_pipeline_2.evals.runners.expect import load_cases

__all__ = [
    "CASES_PATH",
    "DEFAULT_CORPUS",
    "REPORT_DIR",
    "load_cases",
    "main",
    "run_chat_cases",
    "run_corpus_eval",
]

if __name__ == "__main__":
    raise SystemExit(main())
