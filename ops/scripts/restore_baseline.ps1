# Restore baseline volumes from ops/baseline-volumes/ (Windows PowerShell).
$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$Out = Join-Path $Root "ops\baseline-volumes"
Push-Location $Root
try {
    docker compose --env-file .env down -v
    docker volume create hey-kivi_hindsight_pg0
    docker volume create hey-kivi_kivi2_sqlite
    docker run --rm -v hey-kivi_hindsight_pg0:/data -v "${Out}:/in" alpine `
        sh -c "test -f /in/hindsight_pg0.tar.gz && tar xzf /in/hindsight_pg0.tar.gz -C /data"
    docker run --rm -v hey-kivi_kivi2_sqlite:/data -v "${Out}:/in" alpine `
        tar xzf /in/kivi2_sqlite.tar.gz -C /data
    docker compose --env-file .env up -d
    Write-Host "Restored baseline volumes; verify GET /stats/golden_goose_eval_user"
}
finally {
    Pop-Location
}
