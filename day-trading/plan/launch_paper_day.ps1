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
if ($guard -notmatch "TRADING") { Log "abort: not a trading day ($($guard.Trim()))"; exit 0 }

# 2. No-double-launch: day file already present?
if ((Test-Path "$root\day-trading\data\paper_days\$day.json") -or
    (Test-Path "$root\day-trading\data\paper_days\$day.md")) {
    Log "abort: day file for $day already exists (session already running)"; exit 0
}

# 3. Headless launch. Auth failure (login expired) is the known risk: claude
#    exits non-zero fast -> flag file so the interactive session / user sees it.
$claude = "C:\Users\My PC\.local\bin\claude.exe"
$prompt = @'
You are launched HEADLESS by Windows Task Scheduler (\Stocks\C37MorningLaunch) to run today's ENTIRE C37 paper-trading session end-to-end. You have FULL AUTHORITY and NOBODY IS READING YOUR REPLIES: never ask a question, never end your turn early, never stop because something looks ambiguous or because OTHER files in the repo are uncommitted (a parallel campaign session owns those; ignore them completely). Your turn ends ONLY when the session is closed after 15:00 ET with the EOD ledger committed and pushed.

FIRST ACTION, before anything else: write the day-file skeleton data/paper_days/{today}.json (mode, config C37, empty trades list) and commit it -- this is the liveness signal the watchdog and backup launcher key on.

Then: read C:\cornell\stocks-automation\.claude\skills\daytrading-morning.md and follow the TOP section exactly (HISTORY below never overrides). NO REAL ORDERS EVER; ONE position at a time; flat $15k tickets ($10k last) to $100k/day; entries until 14:30; all exits by 15:00 with the 14:57 ladder. Use the rank command (never hand-rank); coordinator-owned Trigger C 1-minute polling ([TAKEABLE NOW] only, never [STALE], no delegated pattern detection); crossed-set latch; fill-arming rule at every arming; SPREAD/DEPTH/CHASE vetoes as three separate rates; clock rule (TZ env broken: ET = UTC-4, Monitors on UTC); paper_watch as foreground one-shots; get_equity_historicals batched <=10 with returned-set assert. HALAL: only verdict PASS is armable; CANNOT-VERIFY is not tradeable. Benchmark $1,517/traded day. If monitoring dies mid-position, follow OUTAGE / DEAD-MONITOR SETTLEMENT. TAKE NOTES AND COMMIT AND PUSH THE LEDGER AS THE DAY RUNS (stage only your own files -- git add specific paths, never -A). Write data/paper_days/{today}.json and .md, update NOTES-DAYTRADING.md, EOD summary vs $1,517/day, final commit and push.
'@
Log "starting headless claude session"
# Marker BEFORE launch: the in-session backup cron (06:25) treats this flag as
# SKIP, closing the 5-minute double-launch race while the headless session is
# still writing its day-file skeleton.
New-Item -ItemType File -Path "$root\day-trading\data\paper_days\LAUNCHED_BY_SCHEDULER_$day.flag" -Force | Out-Null
Set-Location $root
$p = Start-Process -FilePath $claude -ArgumentList @("-p", $prompt, "--permission-mode", "acceptEdits") `
     -RedirectStandardOutput "$root\day-trading\data\scheduler_stdout_$day.txt" `
     -RedirectStandardError  "$root\day-trading\data\scheduler_stderr_$day.txt" `
     -NoNewWindow -PassThru
# Liveness = the day-file skeleton the prompt orders as FIRST ACTION.
# 12-minute deadline; a headless one-shot that answers-and-exits without a
# day file (the 2026-08-21 failure) is caught here, flag removed so the
# 06:45 in-session backup cron launches instead.
Start-Sleep -Seconds 720
$alive = (Test-Path "$root\day-trading\data\paper_days\$day.json") -or
         (Test-Path "$root\day-trading\data\paper_days\$day.md")
if ($alive) {
    Log "headless session confirmed live (day file present, pid $($p.Id))"
} else {
    Log "LAUNCH FAILED: no day file after 12 min (exited=$($p.HasExited) code=$($p.ExitCode)) -- clearing scheduler flag for the backup cron"
    Remove-Item "$root\day-trading\data\paper_days\LAUNCHED_BY_SCHEDULER_$day.flag" -ErrorAction SilentlyContinue
    New-Item -ItemType File -Path "$root\day-trading\data\paper_days\LAUNCH_FAILED_$day.flag" -Force | Out-Null
}
