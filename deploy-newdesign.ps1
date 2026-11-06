# Bygger det alternative design (newdesign/) og publicerer det til protek.dk/newdesign på NAS'en.
# Kør: powershell -NoProfile -File deploy-newdesign.ps1
# Rører ikke hovedsitet; kun mappen \newdesign spejles. Vite giver filerne hash-navne, så Cloudflare-cache ikke er et problem.
$ErrorActionPreference = 'Stop'
$src = Join-Path $PSScriptRoot 'newdesign'
$dst = '\\nas.protek.dk\web\protek.dk\newdesign'
if (-not (Test-Path (Split-Path $dst))) { throw "Kan ikke nå $(Split-Path $dst)" }

Push-Location $src
try {
  if (-not (Test-Path node_modules)) { npm ci; if ($LASTEXITCODE) { throw 'npm ci fejlede' } }
  npx vite build
  if ($LASTEXITCODE) { throw 'vite build fejlede' }
} finally { Pop-Location }

robocopy "$src\dist" $dst /MIR /XF Thumbs.db /NFL /NDL /NJH /NJS /NP /R:1 /W:1 | Out-Null
if ($LASTEXITCODE -ge 8) { throw "robocopy fejlede ($LASTEXITCODE)" }
$global:LASTEXITCODE = 0
Write-Host "Publiceret til $dst  ->  https://protek.dk/newdesign/"
