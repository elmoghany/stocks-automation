#!/bin/bash
#SBATCH --job-name=chr2_all
#SBATCH -p gpu
#SBATCH --gres=gpu:1
#SBATCH --exclude=coecis-compute-02,hariharan-compute-02,hinton,joachims-compute-02,nikola-compute-[01-05],sablab-gpu-[01-07],snavely-compute-[04,06,07,09-12],tripods-compute-02,unicorn-compute-05
#SBATCH --time=06:00:00
#SBATCH --mem=24g
#SBATCH --cpus-per-task=4
#SBATCH --output=/home/me484/chronos2/out/all_%j.out
#SBATCH --error=/home/me484/chronos2/out/all_%j.out
set -x
hostname; nvidia-smi -L
. /home/me484/miniconda3/etc/profile.d/conda.sh
conda activate /home/me484/chronos2/env
cd /home/me484/chronos2
bash pipeline.sh small autogluon/chronos-2-small
bash pipeline.sh base amazon/chronos-2
