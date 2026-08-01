$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot

try {
  if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    throw 'Node.js 24 is required. Install the version from .node-version first.'
  }

  python -m uv --version | Out-Null
  if ($LASTEXITCODE -ne 0) {
    throw 'uv is required. Run: python -m pip install --user uv'
  }

  npm ci
  python -m uv sync --project pipeline --frozen
  Write-Output 'NewsEviday dependencies are ready.'
}
finally {
  Pop-Location
}
