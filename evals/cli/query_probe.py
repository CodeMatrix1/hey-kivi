"""CLI entry: HTTP /chat probe. Implementation in evals.runners.probe."""

from hindsight_pipeline_2.evals.runners.probe import main, run_probe

__all__ = ["main", "run_probe"]

if __name__ == "__main__":
    raise SystemExit(main())
