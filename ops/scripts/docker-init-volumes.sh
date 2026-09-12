#!/bin/sh
# Seed Docker volumes from baked-in baseline tarballs (first run only).
set -e

BASE=/app/hindsight_pipeline_2/ops/baseline-volumes

if [ ! -f "$BASE/hindsight_pg0.tar.gz" ] || [ ! -f "$BASE/kivi2_sqlite.tar.gz" ]; then
  echo "ERROR: baseline tarballs missing in image at $BASE" >&2
  exit 1
fi

restore_volume() {
  target="$1"
  tarball="$2"
  marker="$3"
  label="$4"

  if [ -f "$marker" ]; then
    echo "$label volume already initialized; skipping."
    return 0
  fi

  echo "Restoring $label volume from $(basename "$tarball") ..."
  find "$target" -mindepth 1 -maxdepth 1 -exec rm -rf {} +
  tar xzf "$tarball" -C "$target"
  touch "$marker"
  echo "$label volume ready."
}

restore_volume /hindsight "$BASE/hindsight_pg0.tar.gz" /hindsight/.baseline_restored "Hindsight"
restore_volume /sqlite "$BASE/kivi2_sqlite.tar.gz" /sqlite/.baseline_restored "SQLite"
