# check.ps1 — Full quality gate for Warframe Archives (Windows / PowerShell)
# Usage: .\scripts\check.ps1
# Runs: ruff linting → Python compilation → pytest suite
# All three must pass for a "green" build.

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Step([string]$label, [scriptblock]$block) {
    Write-Host ""
    Write-Host "=== $label ===" -ForegroundColor Cyan
    & $block
    if ($LASTEXITCODE -ne 0) {
        Write-Host "FAILED: $label" -ForegroundColor Red
        exit $LASTEXITCODE
    }
    Write-Host "OK: $label" -ForegroundColor Green
}

Step "1/3  Ruff lint" {
    python -m ruff check
}

Step "2/3  Compile check" {
    python -m compileall -q warframe_lore
}

Step "3/3  Test suite" {
    python -m pytest -q
}

Write-Host ""
Write-Host "All checks passed." -ForegroundColor Green

