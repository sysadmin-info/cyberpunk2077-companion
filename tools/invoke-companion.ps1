# Forward the CLI arguments to one application, in PATH order.
$ErrorActionPreference = 'Stop'
$Entry = Join-Path (Split-Path -Parent $PSScriptRoot) 'cp2077_companion.py'
foreach ($Name in 'py', 'python') {
    $Application = Get-Command -Name $Name -CommandType Application -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($null -eq $Application) { continue }

    $Prefix = @()
    if ($Name -eq 'py') { $Prefix = @('-3') }
    & $Application.Path @Prefix $Entry @args
    exit $LASTEXITCODE
}
throw 'Python 3.10+ required: neither py nor python was found in PATH.'
