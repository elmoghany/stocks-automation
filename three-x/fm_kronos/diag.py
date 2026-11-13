"""Side diagnostics (not part of the shared score): does Kronos beat plain momentum, and how much of its test IC is just trailing return?"""
from pathlib import Path

import numpy as np
import pandas as pd

R = Path(__file__).parent.parent / "results"
px = pd.read_csv(R / "amd_daily_2012_cache.csv", index_col=0, parse_dates=True)
c = px.close
f = pd.read_csv(R / "fm_kronos_forecasts.csv", parse_dates=["date"])
rows = []
for (v, h), g in f.groupby(["variant", "horizon"]):
    p = g.set_index("date").pred_ret
    real = (c.shift(-h) / c - 1).reindex(p.index)
    mom = (c / c.shift(h) - 1).reindex(p.index)  # trailing h-day return, same horizon, known at D
    for name, lo, hi in (("val", "2024-07-01", "2025-06-30"), ("test", "2025-07-01", "2026-11-11")):
        m = (p.index >= lo) & (p.index <= hi) & real.notna()
        pp, rr, mm = p[m], real[m], mom[m]
        # non-overlapping sample (every h-th day) for an honest effective sample size
        k = np.arange(0, m.sum(), h)
        rows.append(dict(variant=v, h=h, period=name, n=int(m.sum()), n_indep=len(k), ic=pp.corr(rr, method="spearman"), ic_nonoverlap=pp.iloc[k].corr(rr.iloc[k], method="spearman"),
                         corr_with_trailing_ret=pp.corr(mm, method="spearman"), momentum_ic=mm.corr(rr, method="spearman"), mean_pred=pp.mean(), pct_pred_pos=(pp > 0).mean(), mean_real=rr.mean()))
pd.set_option("display.width", 250, "display.max_columns", 30)
out = pd.DataFrame(rows)
out.to_csv(Path(__file__).parent / "diag.csv", index=False)
print(out.to_string(index=False, float_format=lambda v: f"{v:.2f}"))
