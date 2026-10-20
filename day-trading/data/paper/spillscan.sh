#!/bin/sh
# usage: sh data/paper/spillscan.sh rl|r4 GRID_HH:MM SPILLFILE  -- convert spilled run_scan dump and ingest via scan3.py
B=$1; G=$2; F=$3
python data/paper/spill2rows.py "$B" "$F" > /tmp/spill_rows_$B.txt || exit 1
N=$(wc -l < /tmp/spill_rows_$B.txt)
python data/paper/scan3.py "$B" "$G" $N < /tmp/spill_rows_$B.txt
