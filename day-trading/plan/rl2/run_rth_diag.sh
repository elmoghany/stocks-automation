#!/usr/bin/env bash
# Next-steps item #1, run now: does the online-RL arm regain power when the
# extended-hours action space is removed? Same env, same seed, same steps,
# RL2_RTH_ONLY=1 so buys and sells are masked outside 09:30-16:00.
set -u
PY="C:/cornell/venvs/rl/Scripts/python.exe"
cd "C:/cornell/stocks-automation/day-trading"
export OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 RL2_RTH_ONLY=1
echo "=== maskppo leak30 RTH-ONLY seed 0, 250k ==="
"$PY" -u plan/rl2/train.py --algo maskppo --variant leak30 --seed 0 --steps 250000 2>&1
mv plan/rl2/results/rl_maskppo_leak30_s0.json plan/rl2/results/rl_maskppo_leak30_rthonly_s0.json
echo "=== maskppo real RTH-ONLY seed 0, 250k ==="
"$PY" -u plan/rl2/train.py --algo maskppo --variant real --seed 0 --steps 250000 2>&1
mv plan/rl2/results/rl_maskppo_real_s0.json plan/rl2/results/rl_maskppo_real_rthonly_s0.json
echo "RTH DIAG DONE"
