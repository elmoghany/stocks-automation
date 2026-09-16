#!/usr/bin/env bash
# The 250k-step leak30 positive control FAILED (-$88/ticket on test), which
# makes approach 3's null result uninformative at that budget. Re-run the
# control with 3.2x the steps to find out whether the arm has power at all.
set -u
PY="C:/cornell/venvs/rl/Scripts/python.exe"
cd "C:/cornell/stocks-automation/day-trading"
while ! grep -q "^RL ONLINE DONE" plan/rl2/out/rl.log 2>/dev/null; do sleep 30; done
export OMP_NUM_THREADS=2
export MKL_NUM_THREADS=2
echo "=== maskppo leak30 seed 0, 800k steps ==="
"$PY" plan/rl2/train.py --algo maskppo --variant leak30 --seed 0 --steps 800000 2>&1 | grep -v Warning
mv plan/rl2/results/rl_maskppo_leak30_s0.json plan/rl2/results/rl_maskppo_leak30_800k_s0.json
echo "=== maskppo real seed 0, 800k steps ==="
"$PY" plan/rl2/train.py --algo maskppo --variant real --seed 0 --steps 800000 2>&1 | grep -v Warning
mv plan/rl2/results/rl_maskppo_real_s0.json plan/rl2/results/rl_maskppo_real_800k_s0.json
echo "RL POWER DONE"
