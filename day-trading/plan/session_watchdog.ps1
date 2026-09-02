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
if ($guard -match "ERROR" -or $guard -notmatch "TRADING|NO-TRADE") {
    Log "WATCHDOG: CALENDAR ERROR -- $($guard.Trim())"
    New-Item -ItemType File -Path "$root\day-trading\data\paper_days\CALENDAR_ERROR_$day.flag" -Force | Out-Null
    & msg.exe $env:USERNAME "C37 watchdog: CALENDAR ERROR -- $($guard.Trim())" 2>$null
    exit 1
}
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
    # Presence != capability (Day 16): the heartbeat is written only after a
    # green capability probe. Fresh day file + no heartbeat = a session that
    # can write files and do nothing else.
    $hb = "$root\day-trading\data\paper_days\SESSION_ALIVE_$day.flag"
    if (Test-Path $hb) {
        $hage = ((Get-Date) - (Get-Item $hb).LastWriteTime).TotalMinutes
        if ($hage -gt 10) { $alert = "STALE HEARTBEAT: SESSION_ALIVE last touched $([int]$hage) min ago" }
    } else {
        $alert = "NO HEARTBEAT: day file exists but SESSION_ALIVE_$day.flag was never written (capability probe not passed?)"
    }
    # An open book with a dead watcher is the worst case under multi-position rules.
    $openPos = Get-ChildItem "$root\day-trading\data\paper\position_*.json" -ErrorAction SilentlyContinue |
               Where-Object { (Get-Content $_.FullName -Raw) -match ('"date"\s*:\s*"' + $day + '"') }
    if ($openPos) {
        $wa = "$root\day-trading\data\paper_days\WATCH_ALIVE_$day.json"
        if (-not (Test-Path $wa) -or (((Get-Date) - (Get-Item $wa).LastWriteTime).TotalMinutes -gt 3)) {
            $alert = "WATCHER DEAD WITH OPEN BOOK: $($openPos.Count) position file(s) dated $day but no fresh WATCH_ALIVE"
        }
    }
}
if ($alert) {
    Log "WATCHDOG ALERT: $alert"
    New-Item -ItemType File -Path "$root\day-trading\data\paper_days\WATCHDOG_ALERT_$day.flag" -Force | Out-Null
    # pop a desktop message so a human sees it same-day
    & msg.exe $env:USERNAME "C37 paper session: $alert" 2>$null
} else {
    Log "watchdog: session healthy"
}
