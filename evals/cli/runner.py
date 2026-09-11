"""CLI entry: demo-case quality suite. Implementation in evals.runners.quality."""

from hindsight_pipeline_2.evals.paths import DEMO_CASES_PATH, LAST_RUN_PATH
from hindsight_pipeline_2.evals.runners.expect import check_expect, load_cases
from hindsight_pipeline_2.evals.runners.quality import (
    main,
    run_case,
    run_suite,
    setup_case,
)

CASES_PATH = DEMO_CASES_PATH
REPORT_PATH = LAST_RUN_PATH

__all__ = [
    "CASES_PATH",
    "REPORT_PATH",
    "check_expect",
    "load_cases",
    "main",
    "run_case",
    "run_suite",
    "setup_case",
]

if __name__ == "__main__":
    raise SystemExit(main())
