# Publicerer protek.dk til NAS'en. Kør: powershell -File deploy.ps1
# Stempler css/js med indholds-hash (?v=...), så Cloudflare og mobilbrowsere henter nye filer ved hver ændring.
$ErrorActionPreference = 'Stop'
$src = $PSScriptRoot
$dst = '\\nas.protek.dk\web\protek.dk'
if (-not (Test-Path $dst)) { throw "Kan ikke nå $dst" }

$html = [IO.File]::ReadAllText("$src\index.html", [Text.Encoding]::UTF8)
foreach ($f in 'css/scrollcraft.css', 'css/protek.css', 'js/scrollcraft.js') {
  $h = (Get-FileHash ("$src\" + ($f -replace '/', '\')) -Algorithm SHA1).Hash.Substring(0, 10).ToLower()
  $pattern = '(?<=["''])' + [regex]::Escape($f) + '(\?v=[0-9a-f]+)?(?=["''])'
  $html = [regex]::Replace($html, $pattern, ($f + '?v=' + $h))
}
[IO.File]::WriteAllText("$src\index.html", $html, (New-Object Text.UTF8Encoding($true)))

Copy-Item "$src\index.html" "$dst\index.html" -Force
foreach ($d in 'css', 'js', 'img', 'fonts') {
  robocopy "$src\$d" "$dst\$d" /E /XF Thumbs.db *.psd /NFL /NDL /NJH /NJS /NP /R:1 /W:1 | Out-Null
}
Write-Host "Publiceret til $dst"
