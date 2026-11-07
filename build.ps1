# Samler hele protek.dk i .\dist (samme struktur som paa webserveren).
# Koer: powershell -NoProfile -File build.ps1
#   dist\                 forsiden (partikeldesignet, site\)
#   dist\designs\<navn>\  de andre designs (Vite-builds og statiske sites)
#   dist\newdesign*\      omdirigeringer fra de gamle adresser
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$out = Join-Path $root 'dist'

function Build-Vite($dir) {
  Push-Location $dir
  try {
    if (-not (Test-Path node_modules)) { npm ci; if ($LASTEXITCODE) { throw "npm ci fejlede i $dir" } }
    npx vite build --logLevel warn
    if ($LASTEXITCODE) { throw "vite build fejlede i $dir" }
  } finally { Pop-Location }
}

function Copy-Tree($from, $to, [string[]]$excludeDirs = @()) {
  $ra = @($from, $to, '/E', '/XF', 'Thumbs.db', '*.psd', '/NFL', '/NDL', '/NJH', '/NJS', '/NP', '/R:1', '/W:1')
  if ($excludeDirs.Count) { $ra += '/XD'; $ra += $excludeDirs }
  robocopy @ra | Out-Null
  if ($LASTEXITCODE -ge 8) { throw "robocopy fejlede ($LASTEXITCODE): $from" }
  $global:LASTEXITCODE = 0
}

if (Test-Path $out) { Remove-Item $out -Recurse -Force }
New-Item -ItemType Directory $out | Out-Null

# Forsiden
Build-Vite (Join-Path $root 'site')
Copy-Tree (Join-Path $root 'site\dist') $out

# Vite-designs
foreach ($d in 'bauhaus', 'tidende', 'ebru') {
  $src = Join-Path $root "designs\$d"
  Build-Vite $src
  Copy-Tree "$src\dist" "$out\designs\$d"
}

# Statiske designs
Copy-Tree (Join-Path $root 'designs\plakat') "$out\designs\plakat"
Copy-Tree (Join-Path $root 'designs\legacy') "$out\designs\legacy" @('less', 'files', 'maps')

# Gamle adresser -> nye
$moved = @{ 'newdesign' = '/'; 'newdesign2' = '/designs/bauhaus/'; 'newdesign3' = '/designs/tidende/'; 'newdesign4' = '/designs/ebru/' }
foreach ($k in $moved.Keys) {
  $to = $moved[$k]
  New-Item -ItemType Directory "$out\$k" -Force | Out-Null
  $html = "<!doctype html><meta charset=`"utf-8`"><title>Flyttet</title><meta http-equiv=`"refresh`" content=`"0; url=$to`"><link rel=`"canonical`" href=`"https://protek.dk$to`"><script>location.replace('$to'+location.hash)</script><a href=`"$to`">protek.dk$to</a>"
  [IO.File]::WriteAllText("$out\$k\index.html", $html, (New-Object Text.UTF8Encoding($false)))
}

Write-Host "Bygget til $out"
