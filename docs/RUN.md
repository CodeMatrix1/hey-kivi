# RUN.md — Local review guide (Hey Kivi Phase 1)

## Primary review method

```text
REVIEWERS: Restore the included baseline snapshot. Full corpus import is an optional reproducibility path.

PREREQS: Docker, Docker Compose, GROQ_API_KEY in .env
PATH A user_id: golden_goose_eval_user  (pre-loaded in baseline — use for chat probes)
PATH B user_id: corpus_repro_user        (import only — never import into golden_goose_eval_user)
PATH A (primary — do this): restore ops/baseline-volumes/*.tar.gz → compose up → verify /stats → chat probes
PATH B (optional — reproducibility only): compose up → import 500 JSONL as corpus_repro_user → verify reports
  (Path B: ~505 Hindsight retains, 30–90+ min, Groq rate limits — not required for review)
NEVER: Seed demo on golden_goose_eval_user after restore (wipes SQLite for that user)
NEVER: Path B import into golden_goose_eval_user (baseline already contains that corpus)
VERIFY: pytest (offline) → /health → /stats → 3 curl chat probes → optional corpus_runner
RESET: docker compose down -v
```

All commands below assume:

```bash
cd hindsight_pipeline_2
cp .env.example .env   # set GROQ_API_KEY; keep HINDSIGHT_BANK_PREFIX=kivi for Path A
```

### User IDs

| User ID | When to use |
|---------|-------------|
| `golden_goose_eval_user` | **Path A only** — baseline snapshot already has 505 dictations + Hindsight memories for this user. Run §7 chat probes with this id. |
| `corpus_repro_user` | **Path B only** — fresh import of the 500 JSONL to prove reproducibility without overwriting the baseline user. Use this id in §9 import and when chatting after a Path B import. |
| `demo_user` | Developer seed demo only (§4) — never use for review. |

---

## 1. Runtimes and versions

| Component | Version / image |
|-----------|-----------------|
| Python | 3.11+ (`requirements.txt` in this directory) |
| Hey Kivi API | `python -m hindsight_pipeline_2.kivi.api` on port **8002** |
| Hindsight | `ghcr.io/vectorize-io/hindsight:latest` — API **8888**, UI **9999** |
| SQLite | `KIVI2_DB_PATH` (default `artifacts/runtime/kivi.sqlite3` in container) |
| Hey Kivi LLM | **Groq or Gemini only** (`LLM_PROVIDER`) |
| Hindsight LLM | Groq via `HINDSIGHT_API_LLM_*` in compose |

---

## 2. Environment variables

Copy **only** `hindsight_pipeline_2/.env.example` → `hindsight_pipeline_2/.env` (not repo-root mem0 `.env`).

| Variable | Required | Purpose |
|----------|----------|---------|
| `GROQ_API_KEY` | Yes (Groq path) | Hey Kivi + Hindsight container LLM |
| `LLM_PROVIDER` | No | `groq` (default) or `gemini` — **Hey Kivi only**; not OpenAI/LiteLLM |
| `GROQ_MODEL` | With Groq | Hey Kivi model id |
| `GEMINI_API_KEY` / `GEMINI_MODEL` | With Gemini | Hey Kivi alternate provider |
| `KIVI_DEFAULT_USER_ID` | No | UI default `golden_goose_eval_user` (Path A probes) |
| `KIVI_DEFAULT_USER_NAME` | No | Optional UI display name |
| `HINDSIGHT_BASE_URL` | No | Default `http://localhost:8888` |
| `HINDSIGHT_BANK_PREFIX` | No | Default `kivi` — **required for Path A baseline** (`kivi_golden_goose_eval_user`). Use `kivi2` only on empty volumes. |
| `HINDSIGHT_RECALL_BUDGET` | No | Default `mid` |
| `KIVI2_DB_PATH` | No | SQLite path (`artifacts/runtime/kivi.sqlite3` on host; set in compose for Docker) |
| `KIVI_REQUIRE_LLM` | No | `true` (default) |
| `KIVI_SAVE_CHATS` | No | Default `false` in compose (keeps baseline SQLite clean during review) |
| `HINDSIGHT_API_LLM_MODEL` | No | Hindsight container model |
| `HINDSIGHT_API_LLM_GROQ_SERVICE_TIER` | No | Default `on_demand` |
| `HINDSIGHT_RETAIN_MIN_INTERVAL_SECONDS` | No | Import throttle (default `30`) |
| `KIVI_ESTIMATED_LLM_COST_USD` | No | Metrics (default `0`) |
| `KIVI_ESTIMATED_RETAIN_COST_USD` | No | Import cost estimate (default `0`) |

---

## 3. Install dependencies (offline pytest)

```bash
pip install -r requirements.txt
pytest evals/tests -q    # from this directory; pythonpath=.. in pytest.ini (monorepo parent)
```

---

## 4. Developer only — Seed demo

**Not the reviewer path.** `POST /seed` or the UI Seed button (Developer mode) **wipes SQLite dictations** for the current `user_id` and inserts 3 demo rows. Never run on `golden_goose_eval_user` after snapshot restore.

```bash
python -m hindsight_pipeline_2.kivi.seed --user-id demo_user
```

---

## 5. Start Docker Compose

```bash
docker compose --env-file .env up --build -d
curl http://localhost:8002/health
```

**Volumes:** `hey-kivi_hindsight_pg0`, `hey-kivi_kivi2_sqlite`.

### 5b. Path A — Restore baseline snapshot

**Bash (Linux/macOS):**

```bash
bash ops/scripts/restore_baseline.sh
```

**PowerShell (Windows):**

```powershell
docker compose --env-file .env down -v
docker volume create hey-kivi_hindsight_pg0
docker volume create hey-kivi_kivi2_sqlite
docker run --rm -v hey-kivi_hindsight_pg0:/data -v "${PWD}/ops/baseline-volumes:/in" alpine sh -c "test -f /in/hindsight_pg0.tar.gz && tar xzf /in/hindsight_pg0.tar.gz -C /data"
docker run --rm -v hey-kivi_kivi2_sqlite:/data -v "${PWD}/ops/baseline-volumes:/in" alpine tar xzf /in/kivi2_sqlite.tar.gz -C /data
docker compose --env-file .env up -d
```

Expect `GET /stats/golden_goose_eval_user` → `dictations: 505`, `hindsight_memories` ≈ 648.

**Baseline tarball size:** `hindsight_pg0.tar.gz` is ~45 MB (committed for Path A). Plain git is fine; use Git LFS only if your org requires it.

**Save snapshot after a successful Path B import:** `bash ops/scripts/snapshot_baseline.sh` — writes `ops/baseline-volumes/*.tar.gz` (only if you intentionally regenerate baseline from `corpus_repro_user` or a fresh import).

---

## 6. Endpoints

| URL | Purpose |
|-----|---------|
| http://localhost:8002 | Chat UI |
| http://localhost:8002/health | Health + `default_user_id` |
| http://localhost:8002/stats/{user_id} | Dictation + Hindsight counts |
| http://localhost:8888 | Hindsight API |
| http://localhost:9999 | Hindsight admin UI |

---

## 7. Primary chat probes (Path A)

Use `user_id=golden_goose_eval_user` (baseline user — do not re-import corpus for this id):

| # | Message | Expect in `trace` |
|---|---------|-------------------|
| 1 | I am arranging a family visit. Remind me where my sister Maya and my brother Arjun are based. | `decision: answer`, `hindsight_recall`, Pune/Bengaluru in reply or considered |
| 2 | I have a payments team review coming up. Pull together what I have already said about the review and the presentation work, then give me the key points to bring in. | `decision: answer`, payments/presentation context |
| 3 | What is my passport number? | `decision: abstain` |

```bash
curl -s -X POST http://localhost:8002/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is my passport number?", "user_id": "golden_goose_eval_user"}' | jq .trace.decision
```

Optional: find + polish train seats (`find_dictations`, `polish_dictation`).

**After Path B import:** repeat the same three probes with `user_id=corpus_repro_user` (same messages; same expected behaviour once import completes).

---

## 8. Run tests and evals

All commands assume `cd hindsight_pipeline_2` and `pip install -r requirements.txt`.

### 8a. Pytest (offline — no Docker, no API keys)

**76 tests** use `StubMemory` and run on the host in seconds:

```bash
pytest evals/tests -q                      # all tiers
pytest evals/tests -v --tb=short      # verbose
pytest evals/tests/unit -q            # find, lexical, routing only
pytest evals/tests/agent -q           # full HeyKiviAgent turns
pytest evals/tests/corpus -q          # JSONL import + ingest reports
pytest evals/tests/contract -q        # FastAPI /health + /chat shape
pytest evals/tests/scenario -q        # JSON case runners (stub backend)
```

Folder layout and per-file test inventories: see [evals/README.md](../evals/README.md) and the module docstring at the top of each `evals/**/test_*.py`.

### 8b. JSON case runners (stub — offline)

```bash
python -m hindsight_pipeline_2.evals.cli.runner --backend stub
python -m hindsight_pipeline_2.evals.cli.corpus_runner --backend stub --limit 5
```

Reports: `artifacts/evals/last_run.json` (offline stub), `artifacts/reports/<stem>_<timestamp>.json`, and pinned `artifacts/reports/query_probe.latest.json` after `query_probe`.

### 8c. Docker integration (live Hindsight + API)

Requires **Path A or B** (§5–§5b): `docker compose up -d`, snapshot restored or corpus imported, `GROQ_API_KEY` in `.env`.

**From the host** (stack listening on localhost):

```bash
# Quality suite against real Hindsight (Groq calls) — Path A user
python -m hindsight_pipeline_2.evals.cli.runner --backend hindsight

# Corpus import + query probes — use corpus_repro_user for Path B imports
python -m hindsight_pipeline_2.evals.cli.corpus_runner \
  --backend hindsight \
  --user-id corpus_repro_user

# HTTP probe: POST every query_cases.json message to /chat (Path A: golden_goose_eval_user)
# Writes artifacts/reports/query_probe_<timestamp>.json and query_probe.latest.json
python -m hindsight_pipeline_2.evals.cli.query_probe --base-url http://localhost:8002

# Path B after import: probe the repro user
python -m hindsight_pipeline_2.evals.cli.query_probe \
  --base-url http://localhost:8002 \
  --user-id corpus_repro_user
```

**Inside the running container** (uses `http://hindsight:8888` automatically):

```bash
docker compose --env-file .env exec hey-kivi \
  python -m hindsight_pipeline_2.evals.cli.corpus_runner \
    --backend hindsight --limit 5 --user-id corpus_repro_user

docker compose --env-file .env exec hey-kivi \
  python -m hindsight_pipeline_2.evals.cli.runner --backend hindsight
```

Optional: offline pytest inside the image (same stub tests as §8a):

```bash
docker compose --env-file .env exec hey-kivi \
  bash -c "cd hindsight_pipeline_2 && pytest evals/tests -q"
```

`evals/integration/` documents future `@pytest.mark.integration` host tests; today integration is **CLI runners + query_probe**, not pytest against Docker.

### 8d. After editing query cases

```bash
python -m hindsight_pipeline_2.evals.sync_cases   # copies cases/query_cases.json → web/assets/ for the UI
```

---

## 9. Corpus import (Path B)

**Use `corpus_repro_user` (or any fresh user id).** Do not import into `golden_goose_eval_user` — the Path A baseline already contains that user's 505 dictations and Hindsight bank `kivi_golden_goose_eval_user`. Re-importing would duplicate retains and corrupt the reviewer snapshot.

### JSONL schema

One JSON object per line:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | yes | Stable dictation id (immutable after insert) |
| `asr` | string | yes | Raw / ASR-like transcript (audit, FTS) |
| `formatted` | string | yes | Written transcript (lexical input, polish source) |
| `created_at` | string | yes | ISO-8601 UTC timestamp |
| `metadata` | object | no | e.g. `category`, `source` |

Example line:

```json
{"id": "hist_001", "asr": "my sister maya lives in pune.", "formatted": "My sister Maya lives in Pune.", "created_at": "2026-07-01T07:10:00+00:00", "metadata": {"category": "fact_relationship", "source": "synthetic_transcript"}}
```

### Import command

```bash
docker compose --env-file .env exec hey-kivi \
  python -m hindsight_pipeline_2.kivi.corpus.import_corpus \
    --path /app/hindsight_pipeline_2/data/corpus/kivi_corpus_500_history.jsonl \
    --user-id corpus_repro_user --progress
```

Verify:

```bash
curl http://localhost:8002/stats/corpus_repro_user
```

Expect `dictations: 505` and `hindsight_memories` > 505 after import completes.

Idempotent per user: unchanged rows skipped via `corpus_ingestions`. Reports: `artifacts/reports/<stem>_<timestamp>.json` and `<stem>.latest.json`.

---

## 10. Inspect state

### Recommended (Docker)

```bash
# Path A baseline user
curl http://localhost:8002/stats/golden_goose_eval_user

# Path B after import
curl http://localhost:8002/stats/corpus_repro_user

docker compose --env-file .env exec hey-kivi \
  python -m hindsight_pipeline_2.ops.scripts.state_snapshot --user-id golden_goose_eval_user
ls artifacts/reports/
```

Every `POST /chat` returns `trace` + `metrics`. Hindsight UI: http://localhost:9999.

### SQLite schema (auto-created on first run)

Single file at `KIVI2_DB_PATH`. Tables created by `DictationStore` and `LexicalStore` on startup — no separate migration step.

| Table | Purpose |
|-------|---------|
| `dictations` | ASR + formatted transcripts per `user_id` |
| `dictations_fts` | FTS5 index over formatted + asr (find_dictations) |
| `corpus_ingestions` | Per-user retain provenance (`dictation_id`, `content_hash`, `memory_id`) |
| `interactions` | Chat log (user/assistant turns) |
| `lexical_mappings` | User alias → canonical spelling/name rules |

Legacy columns (`app`, `topic`, `channel`) are dropped automatically if present from older schemas.

---

## 11. Reset

```bash
docker compose --env-file .env down -v
```

---

## Reviewer dry-run checklist

1. `cd hindsight_pipeline_2` → `cp .env.example .env` → set `GROQ_API_KEY`, confirm `HINDSIGHT_BANK_PREFIX=kivi`
2. `pip install -r requirements.txt && pytest evals/tests -q`
3. Path A: restore baseline → `docker compose up -d`
4. `curl localhost:8002/health` → `curl localhost:8002/stats/golden_goose_eval_user`
5. Three chat probes (§7) with `golden_goose_eval_user`
6. Optional Path B: import as `corpus_repro_user` (§9) — never into `golden_goose_eval_user`
7. Optional Docker evals (§8c): `runner --backend hindsight`, `query_probe`
8. `docker compose down -v`
