# Builds all of protek.dk into .\dist (same layout as on the web server).
# Run: powershell -NoProfile -File build.ps1
#   dist\                 front page (the particle design, site\)
#   dist\designs\<name>\  the other designs (Vite builds and static sites)
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$out = Join-Path $root 'dist'

function Build-Vite($dir) {
  Push-Location $dir
  try {
    if (-not (Test-Path node_modules)) { npm ci; if ($LASTEXITCODE) { throw "npm ci failed in $dir" } }
    npx vite build --logLevel warn
    if ($LASTEXITCODE) { throw "vite build failed in $dir" }
  } finally { Pop-Location }
}

function Copy-Tree($from, $to, [string[]]$excludeDirs = @()) {
  $ra = @($from, $to, '/E', '/XF', 'Thumbs.db', '*.psd', '/NFL', '/NDL', '/NJH', '/NJS', '/NP', '/R:1', '/W:1')
  if ($excludeDirs.Count) { $ra += '/XD'; $ra += $excludeDirs }
  robocopy @ra | Out-Null
  if ($LASTEXITCODE -ge 8) { throw "robocopy failed ($LASTEXITCODE): $from" }
  $global:LASTEXITCODE = 0
}

if (Test-Path $out) { Remove-Item $out -Recurse -Force }
New-Item -ItemType Directory $out | Out-Null

# Front page
Build-Vite (Join-Path $root 'site')
Copy-Tree (Join-Path $root 'site\dist') $out

# Vite designs
foreach ($d in 'bauhaus', 'tidende', 'ebru', 'blender') {
  $src = Join-Path $root "designs\$d"
  Build-Vite $src
  Copy-Tree "$src\dist" "$out\designs\$d"
}

# Static designs
Copy-Tree (Join-Path $root 'designs\plakat') "$out\designs\plakat"
Copy-Tree (Join-Path $root 'designs\legacy') "$out\designs\legacy" @('less', 'files', 'maps')

Write-Host "Built to $out"
