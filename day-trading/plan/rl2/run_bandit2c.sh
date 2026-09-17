#!/usr/bin/env bash
# RL v2 iteration sweep C: the live thread.
# feat2 + RTH-only + RAW (not demeaned) target is the best learned row so far
# (-$14.99/ticket, 100th percentile of its matched random control on total AND
# ex-best-day, still negative). Sweep C takes its seed spread, its threshold
# and horizon neighbours, and its shuffled-target control.
set -u
PY="C:/cornell/venvs/rl/Scripts/python.exe"
cd "C:/cornell/stocks-automation/day-trading"
while ! grep -q "^SWEEP B DONE" plan/rl2/out/bandit2b.log 2>/dev/null; do sleep 20; done
B() { echo "=== bandit2 $* ==="; "$PY" -u plan/rl2/bandit2.py --threads 2 --feat feat2 --block 3 --rounds 200 --rth 1 --target net "$@" 2>&1; }
B --q 0.99  --horizon 30 --seed 1
B --q 0.999 --horizon 30
B --q 0.995 --horizon 15
B --q 0.99  --horizon 30 --variant shuffled
B --q 0.99  --horizon 30 --seed 2
echo "SWEEP C DONE"
