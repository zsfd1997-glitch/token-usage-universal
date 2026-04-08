$ErrorActionPreference = "Stop"

Write-Host "Provisioning Windows guest for token-usage-universal..."

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
  Write-Host "Python is not installed. Install Python 3.11+ before collecting evidence."
}

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
  Write-Host "Git is not installed. Install Git if you need to pull or update the repo inside the guest."
}

New-Item -ItemType Directory -Force -Path "C:\workspace-output" | Out-Null

Write-Host "Provisioning finished."
