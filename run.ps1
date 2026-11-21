param(
    [string]$SaveRoot = "$env:USERPROFILE\Saved Games\CD Projekt Red\Cyberpunk 2077",
    [ValidateRange(1,65535)][int]$Port = 8765,
    [switch]$NoOpen,
    [switch]$UpdateCatalog,
    [switch]$NoCatalogDownload
)
$ErrorActionPreference = 'Stop'
if ($UpdateCatalog -and $NoCatalogDownload) { throw 'Choose either -UpdateCatalog or -NoCatalogDownload.' }
$Runner = Join-Path $PSScriptRoot 'tools/invoke-companion.ps1'
if ($UpdateCatalog) {
    & $Runner --update-catalog
    if ($LASTEXITCODE -ne 0) {
        $UpdateExitCode = $LASTEXITCODE
        [Console]::Error.WriteLine('Catalog update failed. Start without -UpdateCatalog to work offline.')
        exit $UpdateExitCode
    }
}
$ServerArgs = @("--save-root", $SaveRoot, "--port", $Port)
if ($NoOpen) { $ServerArgs += "--no-open" }
& $Runner @ServerArgs
exit $LASTEXITCODE
