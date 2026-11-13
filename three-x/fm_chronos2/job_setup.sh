#!/bin/bash
#SBATCH --job-name=chr2_setup
#SBATCH -p gpu
#SBATCH --gres=gpu:1
#SBATCH --time=00:40:00
#SBATCH --mem=16g
#SBATCH --cpus-per-task=4
#SBATCH --output=/home/me484/chronos2/out/setup_%j.out
#SBATCH --error=/home/me484/chronos2/out/setup_%j.out
set -x
hostname; nvidia-smi -L
cd /home/me484/chronos2
/home/me484/miniconda3/bin/conda create -y -q -p /home/me484/chronos2/env python=3.12
. /home/me484/miniconda3/etc/profile.d/conda.sh
conda activate /home/me484/chronos2/env
pip install -q torch "chronos-forecasting>=2.2" pandas pyarrow accelerate peft
python -c "import torch;print(torch.__version__, torch.cuda.is_available())"
cd three-x/fm_chronos2
python -W ignore forecast.py autogluon/chronos-2-small zero_shot ../../out/smoke_zs.csv --limit 16
head -4 ../../out/smoke_zs.csv
python -W ignore finetune.py autogluon/chronos-2-small ../../out/smoke_ft --set peers --val_from 2024-01-01 --steps 20 --lr 1e-5 --ctx 256 --batch 32
ls ../../out/smoke_ft ../../out/smoke_ft/*
python -W ignore forecast.py ../../out/smoke_ft/finetuned-ckpt ft_peers ../../out/smoke_ft.csv --limit 16
head -4 ../../out/smoke_ft.csv
