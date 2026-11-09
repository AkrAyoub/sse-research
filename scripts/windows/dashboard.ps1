$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$exe = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path $exe)) { throw 'Run scripts/windows/test.ps1 before starting the dashboard.' }
if (-not $env:SSE_CONTROL_TOKEN) {
  $bytes = New-Object byte[] 32
  $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
  try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
  $env:SSE_CONTROL_TOKEN = -join ($bytes | ForEach-Object { $_.ToString('x2') })
}
Write-Host 'SSE control plane' -ForegroundColor Cyan
Write-Host 'URL: http://127.0.0.1:8800'
Write-Host ('Local administrator token: ' + $env:SSE_CONTROL_TOKEN) -ForegroundColor Yellow

Push-Location $root
try {
  & $exe -m uvicorn api:app --app-dir apps/control-plane --host 127.0.0.1 --port 8800
} finally { Pop-Location }
