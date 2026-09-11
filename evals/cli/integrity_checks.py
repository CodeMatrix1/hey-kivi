"""Integrity contract suite. Implementation in evals.runners.integrity."""

from hindsight_pipeline_2.evals.paths import INTEGRITY_CASES_PATH
from hindsight_pipeline_2.evals.runners.integrity import (
    CASES_PATH,
    load_cases,
    make_harness,
    run_case,
    run_integrity_suite,
)

__all__ = [
    "CASES_PATH",
    "INTEGRITY_CASES_PATH",
    "load_cases",
    "make_harness",
    "run_case",
    "run_integrity_suite",
]

if __name__ == "__main__":
    from hindsight_pipeline_2.evals.runners.quality import main as quality_main
    import sys

    raise SystemExit(quality_main(["--integrity"] + sys.argv[1:]))
