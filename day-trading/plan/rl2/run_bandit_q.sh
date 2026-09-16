#!/usr/bin/env bash
set -u
PY="C:/cornell/venvs/rl/Scripts/python.exe"
cd "C:/cornell/stocks-automation/day-trading"
for q in 0.999 0.995 0.99; do
  echo "=== bandit real h30 s0 minq $q ==="
  "$PY" plan/rl2/bandit.py --horizon 30 --variant real --seed 0 --minq $q --threads 2 2>&1 | grep -v Warning
done
for q in 0.999; do
  for s in 1 2; do
    echo "=== bandit real h30 s$s minq $q ==="
    "$PY" plan/rl2/bandit.py --horizon 30 --variant real --seed $s --minq $q --threads 2 2>&1 | grep -v Warning
  done
  echo "=== bandit shuffled h30 s0 minq $q ==="
  "$PY" plan/rl2/bandit.py --horizon 30 --variant shuffled --seed 0 --minq $q --threads 2 2>&1 | grep -v Warning
done
echo "BANDITQ DONE"
