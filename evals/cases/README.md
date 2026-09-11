# Eval case JSON

| File | Used by |
|------|---------|
| `demo_cases.json` | `runners/quality.py`, `test_runners` |
| `query_cases.json` | `runners/corpus.py`, `runners/probe.py`, UI query library |
| `integrity.json` | `runners/integrity.py`, `test_runners` |

Edit `query_cases.json` then run `python -m hindsight_pipeline_2.evals.sync_cases` to update the chat UI copy.
