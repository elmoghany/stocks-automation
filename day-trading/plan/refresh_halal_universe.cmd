@echo off
rem Monthly halal-universe refresh (1st of each month, Task Scheduler:
rem \Stocks\HalalUniverseRefresh). Rebuilds the pre-screened halal list
rem the 5-minute scanner trades from. Log goes next to the data so the
rem morning agent can verify freshness and commit the refreshed lists.
cd /d C:\cornell\stocks-automation\day-trading
python plan\build_halal_universe.py --refresh > data\halal_refresh.log 2>&1
