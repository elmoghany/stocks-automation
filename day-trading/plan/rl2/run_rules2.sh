#!/usr/bin/env bash
# RL v2 iteration: approach-4 search with RTH-only entries and a bigger budget.
set -u
cd "C:/cornell/stocks-automation/day-trading"
while ! grep -q "^RL POWER DONE" plan/rl2/out/rl_power.log 2>/dev/null; do sleep 30; done
export OMP_NUM_THREADS=1
for s in 0 1 2 3 4; do
  echo "=== rules2 holdout seed $s ==="
  python -u plan/rl2/rules2.py --mode holdout --seed $s 2>&1
done
echo "RULES2 HOLDOUT DONE"
echo "=== rules2 walk-forward seed 0 ==="
python -u plan/rl2/rules2.py --mode wf --seed 0 2>&1
echo "RULES2 DONE"
