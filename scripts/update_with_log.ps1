# Run data update and append stdout/stderr to logs\update-YYYYMMDD.log

$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $PSScriptRoot
$LogDir = Join-Path $Root "logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

$stamp = Get-Date -Format "yyyy-MM-dd"
$logFile = Join-Path $LogDir ("update-{0}.log" -f $stamp)
$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) {
    $msg = "[{0}] ERROR: python not found in PATH" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
    Add-Content -Path $logFile -Value $msg -Encoding UTF8
    exit 1
}

$script = Join-Path $Root "scripts\run_all.py"
$header = @"
============================================================
[{0}] start update
  root   = $Root
  python = $python
  script = $script
============================================================
"@ -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
Add-Content -Path $logFile -Value $header -Encoding UTF8

Push-Location $Root
try {
    & $python $script *>> $logFile
    $code = $LASTEXITCODE
} catch {
    Add-Content -Path $logFile -Value ("EXCEPTION: {0}" -f $_) -Encoding UTF8
    $code = 1
} finally {
    Pop-Location
}

$footer = "[{0}] exit={1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $code
Add-Content -Path $logFile -Value $footer -Encoding UTF8
Add-Content -Path $logFile -Value "" -Encoding UTF8
exit $code