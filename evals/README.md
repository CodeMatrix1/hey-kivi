# Hey Kivi evals

## Layout

```
evals/
  cases/                 # JSON case definitions
  runners/               # CLI implementations (quality, corpus, probe, integrity)
  cli/                   # python -m entry shims
  tests/                 # pytest tiers
    unit/
    agent/
    corpus/
    contract/
    scenario/
  integration/           # Docker+Hindsight notes
  conftest.py
  paths.py, sync_cases.py
```

Generated eval output: `../artifacts/evals/` (e.g. `last_run.json`).

## Pytest tiers

| Folder | File | What it covers |
|--------|------|----------------|
| `tests/unit/` | `test_find.py` | FTS5 find, find_params, dictation selection |
| `tests/unit/` | `test_lexical.py` | Extract, store, resolve lexical mappings |
| `tests/unit/` | `test_routing.py` | Interpret rules, cross-recall, provenance cards |
| `tests/agent/` | `test_agent.py` | Full chat turns, metrics, save_chats |
| `tests/corpus/` | `test_corpus.py` | JSONL import, checkpoints, formatting |
| `tests/contract/` | `test_api.py` | HTTP API response contract |
| `tests/scenario/` | `test_runners.py` | demo_cases + query_cases + integrity JSON runners |

## Commands

```bash
cd hindsight_pipeline_2
pytest evals/tests -q
pytest evals/tests/unit -q
python -m hindsight_pipeline_2.evals.cli.runner --backend stub
python -m hindsight_pipeline_2.evals.cli.corpus_runner --backend hindsight
python -m hindsight_pipeline_2.evals.sync_cases
```

After editing `cases/query_cases.json`, run `sync_cases` to update `web/assets/query_cases.json`.
