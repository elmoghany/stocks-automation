# \Stocks\C37Watchdog -- 12:00 ET weekday check that a session is alive.
# A dead session mid-position went unnoticed for a full day once (login expiry,
# 2026-08-17): position orphaned, Tuesday missed entirely. This makes death
# visible same-day. It never trades and never settles -- visibility only.
$ErrorActionPreference = "Continue"
$root = "C:\cornell\stocks-automation"
$log  = "$root\day-trading\data\scheduler_log.txt"
$day  = (Get-Date).ToString("yyyy-MM-dd")
function Log($m) { Add-Content -Path $log -Value "$((Get-Date).ToString('yyyy-MM-dd HH:mm:ss')) $m" -Encoding utf8 }

$guard = & python "$root\day-trading\plan\market_calendar.py" 2>&1 | Out-String
if ($guard -notmatch "TRADING") { exit 0 }

$json = "$root\day-trading\data\paper_days\$day.json"
$md   = "$root\day-trading\data\paper_days\$day.md"
$alert = $null
if (-not ((Test-Path $json) -or (Test-Path $md))) {
    $alert = "NO SESSION: no day file for $day by 12:00 ET"
} else {
    $f = if (Test-Path $json) { Get-Item $json } else { Get-Item $md }
    $age = ((Get-Date) - $f.LastWriteTime).TotalMinutes
    if ($age -gt 30) { $alert = "STALE SESSION: $($f.Name) last written $([int]$age) min ago" }
}
if ($alert) {
    Log "WATCHDOG ALERT: $alert"
    New-Item -ItemType File -Path "$root\day-trading\data\paper_days\WATCHDOG_ALERT_$day.flag" -Force | Out-Null
    # pop a desktop message so a human sees it same-day
    & msg.exe $env:USERNAME "C37 paper session: $alert" 2>$null
} else {
    Log "watchdog: session healthy"
}
