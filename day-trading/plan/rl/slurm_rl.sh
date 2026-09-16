#!/bin/bash
# RL-SERIES (2026-09-16): one SLURM array task = one (algo, variant, seed).
# Submit from /share/taylor/me484/stocks-rl:
#   sbatch --array=0-N%12 slurm_rl.sh
# The grid is in grid.txt, one "algo variant seed steps" per line.
#SBATCH --job-name=stocks-rl
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=06:00:00
#SBATCH --output=/share/taylor/me484/stocks-rl/logs/%A_%a.out
#SBATCH --error=/share/taylor/me484/stocks-rl/logs/%A_%a.out

set -euo pipefail
cd /share/taylor/me484/stocks-rl
export PYTHONPATH=/share/taylor/me484/stocks-rl/pylibs
export TMPDIR=/share/taylor/me484/tmp
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4
PY=/share/taylor/me484/venvs/vllm/bin/python

LINE=$(sed -n "$((SLURM_ARRAY_TASK_ID + 1))p" grid.txt)
read -r ALGO VARIANT SEED STEPS <<< "$LINE"
echo "task $SLURM_ARRAY_TASK_ID -> $ALGO $VARIANT seed=$SEED steps=$STEPS on $(hostname)"
$PY train.py --algo "$ALGO" --variant "$VARIANT" --seed "$SEED" \
    --steps "$STEPS" --evals 10 --device cpu
