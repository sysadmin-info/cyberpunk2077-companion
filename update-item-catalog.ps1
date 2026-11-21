# Explicit download only. Delegates verification and atomic installation to Python.
param([switch]$Quiet)
$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'tools/invoke-companion.ps1') --update-catalog
exit $LASTEXITCODE
