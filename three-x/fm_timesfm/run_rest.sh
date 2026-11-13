#!/bin/bash
#SBATCH -J timesfm_amd2
#SBATCH -p taylor
#SBATCH --gres=gpu:nvidia_a40:1
#SBATCH --mem=24g
#SBATCH --cpus-per-task=4
#SBATCH -t 04:00:00
#SBATCH --requeue
#SBATCH -o /home/me484/timesfm_fm/slurm_%j.out
cd /home/me484/timesfm_fm
export PYTHONPATH=/home/me484/timesfm_fm
export HF_HOME=/home/me484/timesfm_fm/hf
export PYTHONUNBUFFERED=1
nvidia-smi --query-gpu=name,driver_version --format=csv
PY=./env/bin/python
$PY -c "import torch,sys;ok=torch.cuda.is_available();print('cuda',ok,torch.version.cuda);sys.exit(0 if ok else 1)" || exit 1
$PY tfm.py hfcheck --out hfcheck.json
$PY tfm.py ft --variant ft_amd --adapter adapter_ft_amd
$PY tfm.py fcft --variant ft_amd --adapter adapter_ft_amd --out fc_ft_amd.csv
$PY tfm.py ft --variant ft_peers --adapter adapter_ft_peers
$PY tfm.py fcft --variant ft_peers --adapter adapter_ft_peers --out fc_ft_peers.csv
echo ALL_DONE
