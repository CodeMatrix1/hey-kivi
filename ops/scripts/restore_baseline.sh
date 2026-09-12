#!/usr/bin/env bash
# Restore baseline volumes from ops/baseline-volumes/
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUT="$ROOT/ops/baseline-volumes"
COMPOSE="-f $ROOT/docker-compose.yml"
docker compose --env-file "$ROOT/.env" $COMPOSE down -v
docker volume create hey-kivi_hindsight_pg0
docker volume create hey-kivi_kivi2_sqlite
docker run --rm -v hey-kivi_hindsight_pg0:/data -v "$OUT:/in" alpine \
  sh -c 'test -f /in/hindsight_pg0.tar.gz && tar xzf /in/hindsight_pg0.tar.gz -C /data || echo "skip hindsight_pg0 (missing tarball)"'
docker run --rm -v hey-kivi_kivi2_sqlite:/data -v "$OUT:/in" alpine \
  sh -c 'test -f /in/kivi2_sqlite.tar.gz && tar xzf /in/kivi2_sqlite.tar.gz -C /data'
docker compose --env-file "$ROOT/.env" $COMPOSE up -d
echo "Restored baseline volumes; verify GET /stats/golden_goose_eval_user"
