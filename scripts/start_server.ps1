# Start static site server from project root.
#   powershell -ExecutionPolicy Bypass -File scripts\start_server.ps1 [-Port 8080]

param(
    [int]$Port = 8080
)

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "StarkLab News"
Write-Host ("  root : {0}" -f $Root)
Write-Host ("  url  : http://localhost:{0}/" -f $Port)
Write-Host "  stop : Ctrl+C"
Write-Host ""

python -m http.server $Port