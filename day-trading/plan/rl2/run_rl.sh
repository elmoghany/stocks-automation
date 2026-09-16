#!/usr/bin/env bash
# RL-SERIES v2: approaches 3 (online) and 2 (offline).
# The Cornell cluster was unreachable (VPN down) for this session, so these
# run on the 4-core PC; step budgets are stated in rl2-audit.md.
set -u
PY="C:/cornell/venvs/rl/Scripts/python.exe"
cd "C:/cornell/stocks-automation/day-trading"
export OMP_NUM_THREADS=2
export MKL_NUM_THREADS=2

for s in 0 1 2 3 4; do
  echo "=== maskppo real seed $s ==="
  "$PY" plan/rl2/train.py --algo maskppo --variant real --seed $s --steps 250000 2>&1 | grep -v Warning
done
echo "=== maskppo leak30 seed 0 (positive control) ==="
"$PY" plan/rl2/train.py --algo maskppo --variant leak30 --seed 0 --steps 250000 2>&1 | grep -v Warning
for s in 0 1 2; do
  echo "=== ppo real seed $s ==="
  "$PY" plan/rl2/train.py --algo ppo --variant real --seed $s --steps 250000 2>&1 | grep -v Warning
done
echo "RL ONLINE DONE"
