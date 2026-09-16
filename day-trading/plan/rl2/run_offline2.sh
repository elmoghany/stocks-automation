#!/usr/bin/env bash
set -u
PY="C:/cornell/venvs/rl/Scripts/python.exe"
cd "C:/cornell/stocks-automation/day-trading"
while ! grep -q "^OFFLINE DONE" plan/rl2/out/offline.log 2>/dev/null; do sleep 20; done
export OMP_NUM_THREADS=2
export MKL_NUM_THREADS=2
for a in cql bcq; do
  for s in 0 1; do
    echo "=== offline $a seed $s ==="
    "$PY" plan/rl2/offline.py --algo $a --seed $s --steps 50000 2>&1 | grep -v Warning
  done
done
echo "OFFLINE2 DONE"
