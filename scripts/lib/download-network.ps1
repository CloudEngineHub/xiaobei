# Installation process only; never writes user/machine environment settings.
function Initialize-XiaobeiDownloadNetwork([string]$Root, [string]$NodeExe) {
    if (-not $env:XIAOBEI_GITHUB_PROXY) { return }
    $helper = Join-Path $Root 'browser\scripts\download-network.mjs'
    if (-not (Test-Path $helper)) {
        throw 'This release does not support XIAOBEI_GITHUB_PROXY; install a newer tarball.'
    }
    $json = & $NodeExe $helper --json
    if ($LASTEXITCODE -ne 0) { throw 'Invalid installation download configuration' }
    $network = $json | ConvertFrom-Json
    foreach ($entry in $network) {
        [Environment]::SetEnvironmentVariable($entry.Name, [string]$entry.Value, 'Process')
    }
}
