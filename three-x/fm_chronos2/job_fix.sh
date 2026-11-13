#!/bin/bash
#SBATCH --job-name=chr2_smk
#SBATCH -p gpu
#SBATCH --gres=gpu:1
#SBATCH --exclude=coecis-compute-02,hariharan-compute-02,hinton,joachims-compute-02,nikola-compute-[01-05],sablab-gpu-[01-07],snavely-compute-[04,06,07,09-12],tripods-compute-02,unicorn-compute-05
#SBATCH --time=00:40:00
#SBATCH --mem=16g
#SBATCH --cpus-per-task=4
#SBATCH --output=/home/me484/chronos2/out/fix_%j.out
#SBATCH --error=/home/me484/chronos2/out/fix_%j.out
hostname; nvidia-smi -L
. /home/me484/miniconda3/etc/profile.d/conda.sh
conda activate /home/me484/chronos2/env
python -c "import torch;print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_arch_list())"
cd /home/me484/chronos2/three-x/fm_chronos2
python -W ignore forecast.py autogluon/chronos-2-small zero_shot ../../out/smoke_zs.csv --limit 16
head -4 ../../out/smoke_zs.csv
python -W ignore finetune.py autogluon/chronos-2-small ../../out/smoke_ft --set peers --val_from 2024-01-01 --steps 20 --lr 1e-5 --ctx 256 --batch 64 2>&1 | tail -c 1500
ls ../../out/smoke_ft
python -W ignore forecast.py ../../out/smoke_ft/finetuned-ckpt ft_peers ../../out/smoke_ft.csv --limit 16
head -4 ../../out/smoke_ft.csv
