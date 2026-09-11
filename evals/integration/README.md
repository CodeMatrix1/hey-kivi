# Integration tests (Docker + Hindsight)

Pytest in this package runs **offline** with `StubMemory`. Full-stack integration is exercised via CLI runners (not pytest):

```bash
docker compose --env-file .env up -d
python -m hindsight_pipeline_2.evals.cli.corpus_runner --backend hindsight
python -m hindsight_pipeline_2.evals.cli.query_probe --base-url http://localhost:8002
```

Add `@pytest.mark.integration` tests here when you want host-side pytest against a live stack.
