$ErrorActionPreference = "Stop"

$RepoRoot = "C:\workspace\token-usage-universal"
$OutputDir = "C:\workspace-output"

if (-not (Test-Path $RepoRoot)) {
  throw "Repo root not found: $RepoRoot"
}

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

Push-Location $RepoRoot
try {
  python scripts/token_usage.py release-gate --format json --output-dir $OutputDir
} finally {
  Pop-Location
}

Write-Host "Evidence bundle exported to $OutputDir"
