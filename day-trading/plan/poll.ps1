# Day-19 (2026-08-31) one-command Trigger-C poll.
#
# TRIGGER C LOOP ORDERING (2026-08-21, Day-13 defect): fetch bars -> merge ->
# run `trigger` -> READ THE TAG NOW. The pacing wait is never allowed between
# the trigger call and reading its output. This script does the middle three
# steps in one shot so the read happens immediately after the fetch.
#
# Finds the newest spilled get_equity_historicals dump automatically, so the
# command is identical every poll and nothing has to be retyped.
param(
  [string]$Sym = "NEOV",
  [double]$PrevClose = 3.34,
  [string]$Others = "MOVE YDDL AEHL SAIC NCRA PAVS CTW ANPA"
)
$ErrorActionPreference = "Stop"
$dir = "C:\Users\My PC\.claude\projects\C--cornell-stocks-automation\c86f8a01-b2a3-405a-9fda-5956fcddba66\tool-results"
$f = Get-ChildItem $dir -Filter "*get_equity_historicals*" |
     Sort-Object LastWriteTime -Descending | Select-Object -First 1
$u = (Get-Date).ToUniversalTime()
$et = $u.AddHours(-4).ToString("HH:mm:ss")
Set-Location C:\cornell\stocks-automation\day-trading
$syms = ($Sym + " " + $Others).Trim()
python plan/rh_bars_ingest.py $f.FullName 2026-08-31 ($syms -split '\s+') | Select-Object -Last 2
"--- ET $et ---"
Set-Location C:\cornell\stocks-automation
python day-trading/day-trading.py trigger $Sym --as-of $u.AddHours(-4).ToString("HH:mm")
Set-Location C:\cornell\stocks-automation\day-trading
python plan/armcheck.py $Sym $PrevClose ($u.ToString("yyyy-MM-ddTHH:mm:ss") + "Z") 15000 |
  Select-String -Pattern "ORB high|RTH session|premarket high|last close|coil|TRIGGER|limit ceiling|intended shares|20% size|fill-arming"
