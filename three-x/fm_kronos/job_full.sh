#!/bin/bash
#SBATCH --job-name=kronos_amd
#SBATCH -p gpu
#SBATCH --gres=gpu:1
#SBATCH --time=06:00:00
#SBATCH --mem=24g
#SBATCH --cpus-per-task=6
#SBATCH --output=/home/me484/kronos_amd/out/full_%j.out
#SBATCH --error=/home/me484/kronos_amd/out/full_%j.out
# Order matters for risk: fine-tunes first (short), then forecasts. Every forecast file is resumable.
PY=/home/me484/miniconda3/envs/omnivla/bin/python
R=/home/me484/kronos_amd
cd $R
hostname; nvidia-smi -L; date
TOKB=$R/Kronos_weights/Kronos-Tokenizer-base
ARGS="--repo $R/Kronos --data $R/data --model $R/Kronos_weights/Kronos-small --tokenizer $TOKB"
$PY finetune.py $ARGS --mode amd --out $R/out/ft_amd
$PY finetune.py $ARGS --mode peers --out $R/out/ft_peers
for spec in "zero_shot Kronos_weights/Kronos-small $TOKB" "ft_amd out/ft_amd/best $TOKB" "ft_peers out/ft_peers/best $TOKB" "zero_shot_mini Kronos_weights/Kronos-mini $R/Kronos_weights/Kronos-Tokenizer-2k"; do
  set -- $spec
  $PY forecast.py --repo $R/Kronos --prices $R/data/AMD.csv --model $R/$2 --tokenizer $3 --variant $1 --out $R/out/fc_$1.csv --samples 20 --batch_days 8 --max_context $([ $1 = zero_shot_mini ] && echo 2048 || echo 512)
done
date; echo ALL_DONE
