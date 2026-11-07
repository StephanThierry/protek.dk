# Builds all of protek.dk (build.ps1 -> .\dist) and publishes it to the web server.
# Run: powershell -NoProfile -File deploy.ps1
# Target folder and public URL are read from deploy.config.psd1 (not in git) - see deploy.config.example.psd1.
# The root is NOT mirrored: the web folder holds other things (apk, react, upload ...) that do not live in this repo.
# Only the folders the site owns (assets, models, designs) are mirrored; index.html and img are copied on top.
# Vite gives js/css hashed file names, so the Cloudflare cache never serves stale files.
$ErrorActionPreference = 'Stop'
$cfgPath = Join-Path $PSScriptRoot 'deploy.config.psd1'
if (-not (Test-Path $cfgPath)) { throw "Missing $cfgPath - copy deploy.config.example.psd1 and adjust the values" }
$cfg = Import-PowerShellDataFile $cfgPath
$dst = $cfg.Destination
if (-not $dst) { throw "Destination missing in $cfgPath" }
if (-not (Test-Path $dst)) { throw "Cannot reach $dst" }

& (Join-Path $PSScriptRoot 'build.ps1')
$src = Join-Path $PSScriptRoot 'dist'

function Sync($from, $to, [switch]$Mirror) {
  $mode = if ($Mirror) { '/MIR' } else { '/E' }
  robocopy $from $to $mode /XF Thumbs.db /NFL /NDL /NJH /NJS /NP /R:1 /W:1 | Out-Null
  if ($LASTEXITCODE -ge 8) { throw "robocopy failed ($LASTEXITCODE): $from" }
  $global:LASTEXITCODE = 0
}

Copy-Item "$src\index.html" "$dst\index.html" -Force
Sync "$src\img" "$dst\img"
foreach ($d in 'assets', 'models', 'designs') { Sync "$src\$d" "$dst\$d" -Mirror }

Write-Host "Published to $dst  ->  $($cfg.PublicUrl)"
