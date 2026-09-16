#!/usr/bin/env bash
# RL v2 iteration sweep B: the WIDER feature block (multi-day position +
# opening range), which is the information the first pass did not have.
set -u
PY="C:/cornell/venvs/rl/Scripts/python.exe"
cd "C:/cornell/stocks-automation/day-trading"
B() { echo "=== bandit2 $* ==="; "$PY" -u plan/rl2/bandit2.py --threads 2 --feat feat2 "$@" 2>&1; }
B --rth 1 --target xs  --q 0.99  --horizon 30
B --rth 1 --target xs  --q 0.995 --horizon 60
B --rth 1 --target net --q 0.99  --horizon 30
B --rth 1 --target xs  --q 0.99  --horizon 30 --exit trail:0.02,0.05,0.03,240
B --rth 1 --target xs  --q 0.99  --horizon 30 --variant shuffled
echo "SWEEP B DONE"
