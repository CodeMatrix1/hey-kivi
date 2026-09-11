# Baseline volume snapshots

Restore these tarballs for Path A review (see [docs/RUN.md](../../docs/RUN.md) §5b).

**Important:** this snapshot's Hindsight data uses bank prefix `kivi` (bank id `kivi_golden_goose_eval_user`). Set `HINDSIGHT_BANK_PREFIX=kivi` in `.env` after restore — not `kivi2`, or Hey Kivi will hit an empty bank.

| File | Volume |
|------|--------|
| `hindsight_pg0.tar.gz` | `hey-kivi_hindsight_pg0` |
| `kivi2_sqlite.tar.gz` | `hey-kivi_kivi2_sqlite` |

Generate after a successful Path B import: `ops/scripts/snapshot_baseline.sh` (bash).
