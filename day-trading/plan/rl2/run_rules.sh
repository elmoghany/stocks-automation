#!/usr/bin/env bash
# RL-SERIES v2: repeat the approach-4 holdout search under 4 more seeds.
# One best-on-train rule per seed, each evaluated ONCE on the held-out year.
set -u
cd "C:/cornell/stocks-automation/day-trading"
for s in 1 2 3 4; do
  echo "=== rules holdout seed $s ==="
  OMP_NUM_THREADS=1 python plan/rl2/rules.py --mode holdout --seed $s 2>&1 | grep -v Warning
done
echo "RULES DONE"
