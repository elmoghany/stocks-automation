"""Merge the per-variant forecast files pulled from the cluster into results/fm_kronos_forecasts.csv (the scorer's input)."""
from pathlib import Path

import pandas as pd

HERE = Path(__file__).parent
parts = [pd.read_csv(p, parse_dates=["date"]) for p in sorted((HERE / "out").glob("fc_*.csv"))]
f = pd.concat(parts).drop_duplicates(["date", "variant", "horizon"]).sort_values(["variant", "horizon", "date"])
dst = HERE.parent / "results" / "fm_kronos_forecasts.csv"
f.to_csv(dst, index=False)
print(dst, f.groupby(["variant", "horizon"]).size().to_string())
