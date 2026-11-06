# Bygger design 2 (newdesign2/) og publicerer det til protek.dk/newdesign2 paa NAS'en.
# Koer: powershell -NoProfile -File deploy-newdesign2.ps1
# Roerer ikke hovedsitet; kun mappen \newdesign2 spejles. Vite giver filerne hash-navne, saa Cloudflare-cache ikke er et problem.
$ErrorActionPreference = 'Stop'
$src = Join-Path $PSScriptRoot 'newdesign2'
$dst = '\\nas.protek.dk\web\protek.dk\newdesign2'
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
Write-Host "Publiceret til $dst  ->  https://protek.dk/newdesign2/"
