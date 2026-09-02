# \Stocks\C37MorningLaunch -- durable paper-session launcher (W-campaign 1.3)
# Fires 06:20 ET weekdays via Windows Task Scheduler. Survives Claude session
# death, login expiry (logged loudly), and REPL-busy cron starvation -- the
# three measured causes of late/missed sessions (5 of 8 late, Tue 08-18 missed
# entirely). The in-session cron remains as backup; double-launch is prevented
# by the day-file check here AND in the session prompt.
$ErrorActionPreference = "Continue"
$root = "C:\cornell\stocks-automation"
$log  = "$root\day-trading\data\scheduler_log.txt"
$day  = (Get-Date).ToString("yyyy-MM-dd")
function Log($m) { Add-Content -Path $log -Value "$((Get-Date).ToString('yyyy-MM-dd HH:mm:ss')) $m" -Encoding utf8 }

Log "LAUNCH task fired for $day"

# 1. Trading-day guard (python prints TRADING / NO-TRADE / ERROR)
$guard = & python "$root\day-trading\plan\market_calendar.py" 2>&1 | Out-String
if ($guard -match "ERROR" -or $guard -notmatch "TRADING|NO-TRADE") {
    # ERROR (year outside the calendar, python missing, venv broken) is NOT a
    # holiday. A silent exit here would hide every future launch (2028-01-03).
    Log "CALENDAR ERROR -- launch aborted LOUDLY: $($guard.Trim())"
    New-Item -ItemType File -Path "$root\day-trading\data\paper_days\CALENDAR_ERROR_$day.flag" -Force | Out-Null
    & msg.exe $env:USERNAME "C37 launcher: CALENDAR ERROR -- $($guard.Trim())" 2>$null
    exit 1
}
if ($guard -notmatch "TRADING") { Log "abort: not a trading day ($($guard.Trim()))"; exit 0 }

# 2. No-double-launch: day file already present?
if ((Test-Path "$root\day-trading\data\paper_days\$day.json") -or
    (Test-Path "$root\day-trading\data\paper_days\$day.md")) {
    Log "abort: day file for $day already exists (session already running)"; exit 0
}
if (Test-Path "$root\day-trading\data\paper_days\LAUNCHED_BY_SCHEDULER_$day.flag") {
    # A second fire the same morning (missed-start catch-up, manual re-run)
    # must not double-launch during the 12-minute skeleton window.
    Log "abort: LAUNCHED_BY_SCHEDULER flag already present for $day"; exit 0
}

# 3. Headless launch. Auth failure (login expired) is the known risk: claude
#    exits non-zero fast -> flag file so the interactive session / user sees it.
# PROMPT BUG FIX 2026-08-25: the old multiline $prompt did NOT survive
# Start-Process -ArgumentList quoting -- the Day-15 session received the
# single word "You" and had to recover its mandate by reading this script.
# The mandate now lives in plan/paper_day_prompt.txt; the CLI argument is a
# short single-line pointer that quoting cannot mangle.
$claude = "C:\Users\My PC\.local\bin\claude.exe"
$promptFile = "$root\day-trading\plan\paper_day_prompt.txt"
$prompt = "Read C:\cornell\stocks-automation\day-trading\plan\paper_day_prompt.txt NOW and follow it exactly. It is your full mandate for today's headless C37 paper-trading session."
# PERMISSION BUG FIX 2026-08-26 (it killed Day 16 outright): a headless
# `claude -p --permission-mode acceptEdits` session may WRITE FILES and run
# read-only shell (Get-Date, git status/log) -- and NOTHING ELSE. Every other
# call came back "requires approval" and was auto-denied with no human to ask:
#   python <anything>            -> denied  (no rank / market_calendar / paper_watch)
#   git add / commit / push      -> denied  (no ledger commits)
#   mcp__robinhood-trading__*    -> denied  (no scan, bars, quotes, book)
# acceptEdits auto-approves EDITS ONLY. The session cannot self-grant either:
# Write to .claude/settings.json and .claude/settings.local.json is refused by
# design. So the tool grants MUST come from this command line.
# SAFETY 2026-09-01: NEVER grant the bare server prefix -- it auto-approves
# place_*_order / cancel_* / exercise_*. Only the read-only tools the session
# consumes are listed; .claude/settings.json additionally DENIES every order
# tool, and the session cannot edit that file.
$rh = @("get_equity_quotes","get_equity_historicals","get_equity_price_book",
        "run_scan","get_scans","get_scanner_filter_specs",
        "get_equity_fundamentals","get_financials","get_equity_tradability",
        "get_equity_news","get_earnings_calendar","get_earnings_results",
        "get_index_quotes","get_index_historicals","search",
        "get_portfolio","get_equity_positions","get_accounts") | ForEach-Object { "mcp__robinhood-trading__$_" }
$allowed = (@("Read","Write","Edit","Glob","Grep","TodoWrite","Bash","PowerShell","Monitor","BashOutput","KillShell","WebFetch") + $rh) -join ","
Log "starting headless claude session (allowedTools: $allowed)"
# Marker BEFORE launch: the in-session backup cron (06:45) treats this flag as
# SKIP, closing the 5-minute double-launch race while the headless session is
# still writing its day-file skeleton.
New-Item -ItemType File -Path "$root\day-trading\data\paper_days\LAUNCHED_BY_SCHEDULER_$day.flag" -Force | Out-Null
Set-Location $root
$p = Start-Process -FilePath $claude -ArgumentList @("-p", ('"{0}"' -f $prompt), "--permission-mode", "acceptEdits", "--allowedTools", ('"{0}"' -f $allowed)) `
     -RedirectStandardOutput "$root\day-trading\data\scheduler_stdout_$day.txt" `
     -RedirectStandardError  "$root\day-trading\data\scheduler_stderr_$day.txt" `
     -NoNewWindow -PassThru
# Liveness = the day-file skeleton the prompt orders as FIRST ACTION.
# 12-minute deadline; a headless one-shot that answers-and-exits without a
# day file (the 2026-08-21 failure) is caught here, flag removed so the
# 06:45 in-session backup cron launches instead.
Start-Sleep -Seconds 720
$hb = "$root\day-trading\data\paper_days\SESSION_ALIVE_$day.flag"
$dayfile = (Test-Path "$root\day-trading\data\paper_days\$day.json") -or
           (Test-Path "$root\day-trading\data\paper_days\$day.md")
$alive = (Test-Path $hb) -or $dayfile
if (Test-Path $hb) {
    Log "headless session confirmed live (SESSION_ALIVE heartbeat present, pid $($p.Id))"
} elseif ($dayfile) {
    Log "headless session WEAKLY live: day file present but no SESSION_ALIVE heartbeat yet (pid $($p.Id)) -- capability probe may not have passed"
} else {
    Log "LAUNCH FAILED: no day file after 12 min (exited=$($p.HasExited) code=$($p.ExitCode)) -- clearing scheduler flag for the backup cron"
    Remove-Item "$root\day-trading\data\paper_days\LAUNCHED_BY_SCHEDULER_$day.flag" -ErrorAction SilentlyContinue
    New-Item -ItemType File -Path "$root\day-trading\data\paper_days\LAUNCH_FAILED_$day.flag" -Force | Out-Null
}
