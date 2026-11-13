#!/bin/bash
#SBATCH -J timesfm_sweep
#SBATCH -p taylor
#SBATCH --gres=gpu:nvidia_a40:1
#SBATCH --mem=24g
#SBATCH --cpus-per-task=4
#SBATCH -t 04:00:00
#SBATCH --requeue
#SBATCH -o /home/me484/timesfm_fm/slurm_%j.out
cd /home/me484/timesfm_fm
export PYTHONPATH=/home/me484/timesfm_fm HF_HOME=/home/me484/timesfm_fm/hf PYTHONUNBUFFERED=1
PY=./env/bin/python
$PY -c "import torch,sys;ok=torch.cuda.is_available();print('cuda',ok);sys.exit(0 if ok else 1)" || exit 1
for V in ft_amd ft_peers; do
  for LR in 1e-5 3e-5 1e-4; do
    $PY tfm.py ft --variant $V --adapter adapter_${V}_lr$LR --lr $LR --per_epoch 1600 --epochs 20 --patience 4 --r 8 > log_${V}_lr$LR.txt 2>&1
    grep -E "^epoch|early|saved" log_${V}_lr$LR.txt | tail -n 8
  done
  B=$($PY select_best.py $V)
  $PY tfm.py fcft --variant $V --adapter $B --out fc_$V.csv
done
echo ALL_DONE
