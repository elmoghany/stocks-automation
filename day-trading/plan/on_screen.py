"""OVERNIGHT research step 1: decile screen of every feature on next-overnight return.
Prints mean c_D -> o_{D+1} (bps, equal-weight) by within-day decile, per split.
"""
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from on_lib import load, split_of  # noqa: E402

FEATS_PRE = ["on_mom5", "on_mom20", "on_mom60", "id_mom20", "on_pos20", "tug20", "rev5", "rev20",
             "vol20", "gap", "pgap", "pintra", "lmdv"]
FEATS_CLS = ["intra", "dret", "cloc", "rvol"]


def main():
    u = load()
    u["sp"] = split_of(u.date)
    rng = np.random.default_rng(7)
    u["tb"] = rng.random(len(u))
    print("universe mean on1 by split (bp):",
          (u.groupby("sp").oh1.mean() * 1e4).round(2).to_dict())
    print("per-night eq-wt mean by split:",
          (u.groupby(["sp", "date"]).oh1.mean().groupby("sp").mean() * 1e4).round(2).to_dict())
    for f in FEATS_PRE + FEATS_CLS:
        x = u[np.isfinite(u[f])].copy()
        x["rk"] = x.groupby("date")[f].rank(method="first", pct=True)  # ties ~ row order, fixed below
        x["rk"] = (x[f].rank(pct=True) * 0)  # placeholder to keep dtype
        x = x.sort_values(["date", f, "tb"])
        x["pos"] = x.groupby("date").cumcount()
        x["cnt"] = x.groupby("date")[f].transform("size")
        x["dec"] = (x.pos * 10 // x.cnt).astype(int)
        t = x.groupby(["sp", "dec"]).oh1.mean().unstack() * 1e4
        tag = "PRE" if f in FEATS_PRE else "CLS"
        print(f"\n{f} [{tag}] deciles lo->hi (bp)")
        print(t.round(1).to_string())
    # day-of-week and regime
    print("\nDOW (bp):")
    print((u.groupby(["sp", "dow"]).oh1.mean().unstack() * 1e4).round(1).to_string())
    for f in ["spy_ma50"]:
        print(f"\n{f}:")
        print((u.groupby(["sp", f]).oh1.mean().unstack() * 1e4).round(1).to_string())
    for f in ["spy_r5", "spy_vol20", "vxx_r5", "spy_gap", "spy_intra_cls"]:
        d = u.groupby("date").agg(r=("oh1", "mean"), f=(f, "first"), sp=("sp", "first"))
        d["q"] = pd.qcut(d.f, 5, labels=False, duplicates="drop")
        print(f"\n{f} quintile (date-level, all splits pooled then by split):")
        print((d.groupby(["sp", "q"]).r.mean().unstack() * 1e4).round(1).to_string())
    print("\nearnings overnight (covered names only):")
    c = u[u.earn_cov]
    print((c.groupby(["sp", "earn_on"]).oh1.agg(["mean", "count"])).assign(
        mean=lambda z: z["mean"] * 1e4).round(1).to_string())


if __name__ == "__main__":
    main()
