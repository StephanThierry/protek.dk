# Bygger hele protek.dk (build.ps1 -> .\dist) og publicerer det til NAS'en.
# Koer: powershell -NoProfile -File deploy.ps1
# Roden spejles IKKE, for webmappen indeholder andre ting (apk, react, upload ...), som ikke bor i repoet.
# Kun de mapper, sitet ejer (assets, designs, newdesign*), spejles; index.html og img kopieres ovenpaa.
# Vite giver js/css hash-navne, saa Cloudflare-cache ikke giver gamle filer.
$ErrorActionPreference = 'Stop'
$dst = '\\nas.protek.dk\web\protek.dk'
if (-not (Test-Path $dst)) { throw "Kan ikke naa $dst" }

& (Join-Path $PSScriptRoot 'build.ps1')
$src = Join-Path $PSScriptRoot 'dist'

function Sync($from, $to, [switch]$Mirror) {
  $mode = if ($Mirror) { '/MIR' } else { '/E' }
  robocopy $from $to $mode /XF Thumbs.db /NFL /NDL /NJH /NJS /NP /R:1 /W:1 | Out-Null
  if ($LASTEXITCODE -ge 8) { throw "robocopy fejlede ($LASTEXITCODE): $from" }
  $global:LASTEXITCODE = 0
}

Copy-Item "$src\index.html" "$dst\index.html" -Force
Sync "$src\img" "$dst\img"
foreach ($d in 'assets', 'designs', 'newdesign', 'newdesign2', 'newdesign3', 'newdesign4') { Sync "$src\$d" "$dst\$d" -Mirror }

Write-Host "Publiceret til $dst  ->  https://protek.dk/"
