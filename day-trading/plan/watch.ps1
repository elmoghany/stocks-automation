# Day-19 (2026-08-31) one-command POSITION watch for the open ticket.
#
# Ingests the newest spilled get_equity_historicals dump, rebuilds the
# paper_watch BARS_JSON pinned to the ENTRY BAR, and runs ONE paper_watch
# evaluation as a foreground one-shot (never a background loop - the headless
# turn IS the session, and a backgrounded watcher would be reaped).
#
# SINCE_UTC is mandatory: passing the whole day lets pre-entry bars trip the
# resting stop (CRML false EXIT, 2026-08-25).
param(
  [string]$Sym = "NEOV",
  [double]$Entry = 4.2126,
  [int]$Shares = 1150,
  [double]$PrevClose = 3.34,
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
python plan/paper_watch.py $Sym $Entry $Shares $PrevClose data/paper_days/watch_$Sym.json
