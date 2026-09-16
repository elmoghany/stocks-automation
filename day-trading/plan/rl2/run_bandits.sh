#!/usr/bin/env bash
# RL-SERIES v2: the approach-1 grid. Sequential -- the PC has 4 cores.
set -u
PY="C:/cornell/venvs/rl/Scripts/python.exe"
cd "C:/cornell/stocks-automation/day-trading"
run() { echo "=== $* ==="; "$PY" plan/rl2/bandit.py "$@" 2>&1 | grep -v Warning; }

run --horizon 30 --variant foresight --seed 0
for s in 1 2 3 4; do run --horizon 30 --variant real --seed $s; done
for h in 15 60 120 1000000; do run --horizon $h --variant real --seed 0; done
for s in 0 1 2; do run --horizon 30 --variant shuffled --seed $s; done
run --horizon 30 --variant real --seed 0 --minpred 0.005
run --horizon 30 --variant real --seed 0 --minpred 0.01
echo "GRID DONE"
