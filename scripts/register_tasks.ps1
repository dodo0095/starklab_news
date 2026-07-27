# Register Windows Task Scheduler jobs for 08:00 and 21:00 daily.
# Run from project root:
#   powershell -ExecutionPolicy Bypass -File scripts\register_tasks.ps1

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $Python) {
    Write-Error "python not found in PATH. Install Python first."
}

$Wrapper = Join-Path $Root "scripts\update_with_log.ps1"
if (-not (Test-Path $Wrapper)) {
    Write-Error "wrapper not found: $Wrapper"
}

$LogDir = Join-Path $Root "logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

$PsExe = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
$PsArgs = "-NoProfile -ExecutionPolicy Bypass -File `"$Wrapper`""

function Register-NewsTask {
    param(
        [string]$Name,
        [string]$Time
    )

    $action = New-ScheduledTaskAction -Execute $PsExe -Argument $PsArgs -WorkingDirectory $Root
    $trigger = New-ScheduledTaskTrigger -Daily -At $Time
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 1)
    $principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

    Register-ScheduledTask -TaskName $Name -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force | Out-Null
    Write-Host ("[ok] registered {0} at {1}" -f $Name, $Time)
}

Write-Host "Project root : $Root"
Write-Host "Python       : $Python"
Write-Host "Wrapper      : $Wrapper"
Write-Host ""

Register-NewsTask -Name "StarkLabNews_0800" -Time "08:00"
Register-NewsTask -Name "StarkLabNews_2100" -Time "21:00"

Write-Host ""
Write-Host "Done. Test once:"
Write-Host ("  powershell -NoProfile -ExecutionPolicy Bypass -File `"{0}`"" -f $Wrapper)
Write-Host ""
Write-Host "Query:"
Write-Host "  schtasks /Query /TN StarkLabNews_0800 /V /FO LIST"
Write-Host "  schtasks /Query /TN StarkLabNews_2100 /V /FO LIST"
Write-Host ("Logs: {0}" -f $LogDir)