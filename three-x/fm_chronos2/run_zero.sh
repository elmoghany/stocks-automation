#!/bin/bash
cd /e/stocks-automation/three-x/fm_chronos2
PY=/e/strategy-repos/venvs/chronos/Scripts/python
$PY -W ignore forecast.py autogluon/chronos-2-small zero_shot out_small_zs.csv > log_small_zs.txt 2>&1
$PY -W ignore forecast.py autogluon/chronos-2-small zero_shot_cov out_small_zscov.csv --cov > log_small_zscov.txt 2>&1
$PY -W ignore forecast.py amazon/chronos-2 zero_shot out_base_zs.csv > log_base_zs.txt 2>&1
$PY -W ignore forecast.py amazon/chronos-2 zero_shot_cov out_base_zscov.csv --cov > log_base_zscov.txt 2>&1
echo ALLDONE > zero_done.flag
