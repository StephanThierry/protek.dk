# Bygger design 3 (newdesign3/) og publicerer det til protek.dk/newdesign3 paa NAS'en.
# Koer: powershell -NoProfile -File deploy-newdesign3.ps1
# Roerer ikke hovedsitet; kun mappen \newdesign3 spejles. Vite giver filerne hash-navne, saa Cloudflare-cache ikke er et problem.
$ErrorActionPreference = 'Stop'
$src = Join-Path $PSScriptRoot 'newdesign3'
$dst = '\\nas.protek.dk\web\protek.dk\newdesign3'
if (-not (Test-Path (Split-Path $dst))) { throw "Kan ikke naa $(Split-Path $dst)" }

Push-Location $src
try {
  if (-not (Test-Path node_modules)) { npm ci; if ($LASTEXITCODE) { throw 'npm ci fejlede' } }
  npx vite build
  if ($LASTEXITCODE) { throw 'vite build fejlede' }
} finally { Pop-Location }

robocopy "$src\dist" $dst /MIR /XF Thumbs.db /NFL /NDL /NJH /NJS /NP /R:1 /W:1 | Out-Null
if ($LASTEXITCODE -ge 8) { throw "robocopy fejlede ($LASTEXITCODE)" }
$global:LASTEXITCODE = 0
Write-Host "Publiceret til $dst  ->  https://protek.dk/newdesign3/"
