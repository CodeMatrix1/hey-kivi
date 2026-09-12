#!/usr/bin/env bash
# Save Docker volumes to ops/baseline-volumes/ after a successful import.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUT="$ROOT/ops/baseline-volumes"
COMPOSE="-f $ROOT/docker-compose.yml"
mkdir -p "$OUT"
docker compose --env-file "$ROOT/.env" $COMPOSE stop
docker run --rm -v hey-kivi_hindsight_pg0:/data -v "$OUT:/out" alpine \
  tar czf /out/hindsight_pg0.tar.gz -C /data .
docker run --rm -v hey-kivi_kivi2_sqlite:/data -v "$OUT:/out" alpine \
  tar czf /out/kivi2_sqlite.tar.gz -C /data .
echo "Wrote $OUT/hindsight_pg0.tar.gz and $OUT/kivi2_sqlite.tar.gz"
