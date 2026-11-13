#!/bin/bash
#SBATCH --job-name=kronos_fc
#SBATCH -p gpu
#SBATCH --gres=gpu:1
#SBATCH --time=03:00:00
#SBATCH --mem=16g
#SBATCH --cpus-per-task=4
#SBATCH --output=/home/me484/kronos_amd/out/one_%j.out
#SBATCH --error=/home/me484/kronos_amd/out/one_%j.out
# usage: sbatch job_one.sh VARIANT MODEL_DIR TOKENIZER_DIR MAX_CONTEXT
PY=/home/me484/miniconda3/envs/omnivla/bin/python
R=/home/me484/kronos_amd
cd $R; hostname
$PY forecast.py --repo $R/Kronos --prices $R/data/AMD.csv --model $R/$2 --tokenizer $R/$3 --variant $1 --out $R/out/fc_$1.csv --samples 20 --batch_days 8 --max_context $4
echo ONE_DONE
