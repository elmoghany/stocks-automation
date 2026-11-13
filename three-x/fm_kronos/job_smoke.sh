#!/bin/bash
#SBATCH --job-name=kronos_smoke
#SBATCH -p gpu
#SBATCH --gres=gpu:1
#SBATCH --time=00:25:00
#SBATCH --mem=16g
#SBATCH --cpus-per-task=4
#SBATCH --output=/home/me484/kronos_amd/out/smoke_%j.out
#SBATCH --error=/home/me484/kronos_amd/out/smoke_%j.out
set -x
PY=/home/me484/miniconda3/envs/omnivla/bin/python
R=/home/me484/kronos_amd
cd $R
hostname; nvidia-smi -L
$PY forecast.py --repo $R/Kronos --prices $R/data/AMD.csv --model $R/Kronos_weights/Kronos-small --tokenizer $R/Kronos_weights/Kronos-Tokenizer-base --variant zero_shot --out $R/out/smoke_zs.csv --limit 16 --batch_days 8
cat $R/out/smoke_zs.csv | head -8
$PY finetune.py --repo $R/Kronos --data $R/data --model $R/Kronos_weights/Kronos-small --tokenizer $R/Kronos_weights/Kronos-Tokenizer-base --mode peers --out $R/out/smoke_ft --steps_per_epoch 20 --max_epochs 2
