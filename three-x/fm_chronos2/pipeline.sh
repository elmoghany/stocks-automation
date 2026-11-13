#!/bin/bash
# Usage: pipeline.sh TAG BASE_MODEL ; run from chronos2/three-x/fm_chronos2 inside the venv. Stage A grid per set, pick on 2024H1 holdout, stage B final fit, forecast.
TAG=$1; BASE=$2
O=/home/me484/chronos2/out/$TAG; mkdir -p $O
cd /home/me484/chronos2/three-x/fm_chronos2
python -W ignore forecast.py $BASE zero_shot $O/hold_zs.csv --dfrom 2024-01-02 --dto 2024-06-28 --batch 32 > $O/hold_zs.log 2>&1
python holdout.py $O/hold_zs.csv | tee $O/holdout_table.tsv
for SET in amd peers; do
  for CFG in "100 1e-5" "300 1e-5" "300 5e-5" "1000 5e-5" "1000 2e-4"; do
    set -- $CFG; S=$1; LR=$2; N=A_${SET}_${S}_${LR}
    python -W ignore finetune.py $BASE $O/$N --set $SET --val_from 2024-01-01 --steps $S --lr $LR --ctx 256 --batch 64 > $O/$N.log 2>&1
    python -W ignore forecast.py $O/$N/finetuned-ckpt $N $O/$N.csv --dfrom 2024-01-02 --dto 2024-06-28 --batch 32 > $O/$N.flog 2>&1
    python holdout.py $O/$N.csv | tee -a $O/holdout_table.tsv
    rm -rf $O/$N   # keep disk small
  done
  BEST=$(python - <<PY
import re
best=None
for l in open("$O/holdout_table.tsv"):
    m=re.search(r"A_${SET}_(\d+)_(\S+?)\.csv\tMAE ([0-9.]+)",l)
    if m and (best is None or float(m.group(3))<best[0]): best=(float(m.group(3)),m.group(1),m.group(2))
print(best[1],best[2])
PY
)
  set -- $BEST; S=$1; LR=$2
  echo "SET $SET best steps=$S lr=$LR" | tee -a $O/holdout_table.tsv
  python -W ignore finetune.py $BASE $O/B_$SET --set $SET --steps $S --lr $LR --ctx 256 --batch 64 > $O/B_$SET.log 2>&1
  python -W ignore forecast.py $O/B_$SET/finetuned-ckpt ft_$SET $O/ft_$SET.csv --batch 32 > $O/ft_$SET.flog 2>&1
done
echo PIPELINE_DONE > $O/done.flag
