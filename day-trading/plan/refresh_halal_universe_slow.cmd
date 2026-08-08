@echo off
rem Nightly slow halal-universe build (Task Scheduler:
rem \Stocks\HalalUniverseBuild, 11:30 PM daily). Resumes where it left
rem off; no-data results retry automatically. Single thread + long pace
rem so yfinance's rate limiter is never provoked. Delete this task once
rem halal_universe.json covers the full universe:
rem   schtasks /Delete /TN "\Stocks\HalalUniverseBuild" /F
cd /d C:\cornell\stocks-automation\day-trading
set HALAL_SLOW=1
python plan\build_halal_universe.py >> data\halal_build_nightly.log 2>&1
