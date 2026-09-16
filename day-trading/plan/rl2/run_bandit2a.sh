#!/usr/bin/env bash
# RL v2 iteration sweep A: the three levers the first pass said were binding.
set -u
PY="C:/cornell/venvs/rl/Scripts/python.exe"
cd "C:/cornell/stocks-automation/day-trading"
B() { echo "=== bandit2 $* ==="; "$PY" plan/rl2/bandit2.py --threads 2 "$@" 2>&1 | grep -v Warning; }

B --rth 1 --target xs  --q 0.99  --horizon 30
B --rth 1 --target net --q 0.99  --horizon 30
B --rth 1 --target xs  --q 0.99  --horizon 15
B --rth 1 --target xs  --q 0.999 --horizon 30
B --rth 1 --target xs  --q 0.99  --horizon 30 --exit trail:0.02,0.05,0.03,240
echo "SWEEP A DONE"
