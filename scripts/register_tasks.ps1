# Register Windows Task Scheduler jobs — 每天 4 次自動更新全站資料
#   04:00 (美股收盤後) / 08:00 (台股開盤前) / 14:00 (台股收盤後) / 20:00 (美股開盤前)
# 每次都執行 run_all.py，重抓真實資料（市場/新聞/TSMC/本益比/事件/Fed）並覆蓋。
#
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

# 每天 4 個更新時段
$Tasks = @(
    @{ Name = "StarkLabNews_0400"; Time = "04:00" },  # 美股收盤後
    @{ Name = "StarkLabNews_0800"; Time = "08:00" },  # 台股開盤前
    @{ Name = "StarkLabNews_1400"; Time = "14:00" },  # 台股收盤後
    @{ Name = "StarkLabNews_2000"; Time = "20:00" }   # 美股開盤前
)

Write-Host "Project root : $Root"
Write-Host "Python       : $Python"
Write-Host "Wrapper      : $Wrapper"
Write-Host ""

# 先清掉舊版排程（原本的 21:00，以及不在新清單內的殘留），避免重複觸發
$KeepNames = $Tasks | ForEach-Object { $_.Name }
Get-ScheduledTask -TaskName "StarkLabNews_*" -ErrorAction SilentlyContinue | ForEach-Object {
    if ($KeepNames -notcontains $_.TaskName) {
        Unregister-ScheduledTask -TaskName $_.TaskName -Confirm:$false -ErrorAction SilentlyContinue
        Write-Host ("[--] removed old task {0}" -f $_.TaskName)
    }
}

foreach ($t in $Tasks) {
    Register-NewsTask -Name $t.Name -Time $t.Time
}

Write-Host ""
Write-Host "Done. Test once now:"
Write-Host ("  powershell -NoProfile -ExecutionPolicy Bypass -File `"{0}`"" -f $Wrapper)
Write-Host ""
Write-Host "Query all 4 tasks:"
foreach ($t in $Tasks) {
    Write-Host ("  schtasks /Query /TN {0}" -f $t.Name)
}
Write-Host ("Logs: {0}" -f $LogDir)
