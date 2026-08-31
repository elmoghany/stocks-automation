# Day-19 (2026-08-31) FEED-ONLY step for the running paper_watch background task.
#
# paper_watch.py has an unconditional `while True: ... time.sleep(30)` loop and no
# one-shot flag, so it necessarily runs as a background task. This script does the
# two things the watcher cannot do for itself - pull fresh Robinhood bars and
# rewrite its BARS_JSON - WITHOUT starting a second watcher. Running watch.ps1
# again would spawn a duplicate watcher and the two would fight over
# data/paper/position_{SYM}.json (the exact bug the per-symbol state file was
# introduced to fix on 2026-08-07).
#
# SINCE_UTC is mandatory - pre-entry bars would otherwise trip the resting stop.
param(
  [string]$Sym = "NEOV",
  [string]$SinceUtc = "13:45",
  [string]$Others = "MOVE YDDL AEHL SAIC NCRA PAVS CTW ANPA"
)
$ErrorActionPreference = "Stop"
$dir = "C:\Users\My PC\.claude\projects\C--cornell-stocks-automation\c86f8a01-b2a3-405a-9fda-5956fcddba66\tool-results"
$f = Get-ChildItem $dir -Filter "*get_equity_historicals*" |
     Sort-Object LastWriteTime -Descending | Select-Object -First 1
$u = (Get-Date).ToUniversalTime()
Set-Location C:\cornell\stocks-automation\day-trading
$syms = ($Sym + " " + $Others).Trim()
python plan/rh_bars_ingest.py $f.FullName 2026-08-31 ($syms -split '\s+') | Select-Object -Last 1
"--- ET $($u.AddHours(-4).ToString('HH:mm:ss')) ---"
python plan/csv_to_watchjson.py $Sym 2026-08-31 data/paper_days/watch_$Sym.json $SinceUtc
