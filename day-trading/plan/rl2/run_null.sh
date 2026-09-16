#!/usr/bin/env bash
set -u
cd "C:/cornell/stocks-automation/day-trading"
while ! grep -q "^RULES DONE" plan/rl2/out/rules_seeds.log 2>/dev/null; do sleep 20; done
export OMP_NUM_THREADS=1
echo "=== rules null: draws ==="
python plan/rl2/rules_null.py --mode draws 2>&1 | grep -v Warning
echo "=== rules null: matched random ==="
python plan/rl2/rules_null.py --mode matched 2>&1 | grep -v Warning
echo "NULL DONE"
