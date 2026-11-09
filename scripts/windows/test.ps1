$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
Push-Location $root
try {
  if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    throw 'Python launcher (py) is missing. Install Python 3.12 for Windows first.'
  }
  & py -3.12 --version
  if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 is not available. Install Python.Python.3.12.' }
  $venv = Join-Path $root '.venv'
  $exe = Join-Path $venv 'Scripts\python.exe'
  if (-not (Test-Path $exe)) {
    if (Test-Path $venv) { throw 'Existing .venv is incompatible with native Windows. Rename/delete only .venv and rerun.' }
    & py -3.12 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Virtual environment creation failed.' }
  }
  $version = & $exe --version
  if ($LASTEXITCODE -ne 0 -or $version -notmatch '^Python 3\.12(\.|$)') {
      throw "Project requires Python 3.12, got $version."
  }
  & $exe -m pip install --disable-pip-version-check -r requirements.txt
  if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed.' }
  & $exe -m compileall -q apps services tools tests
  if ($LASTEXITCODE -ne 0) { throw 'Python compileall failed.' }
  & $exe -m unittest discover -s tests -v
  if ($LASTEXITCODE -ne 0) { throw 'Python unit tests failed.' }
  Write-Host 'Python tests completed.' -ForegroundColor Green
} finally { Pop-Location }
