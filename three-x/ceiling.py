"""How much was there to catch? For each 12-month start, the best of every setup in the sweep, with full hindsight.

This is a ceiling, not a strategy: it picks the winner after the period ended. A start date where nothing reached 3x
cannot be a 3x hit for any rule built from these families and stocks. Writes results/ceiling.csv.
"""
import numpy as np
import pandas as pd

import sector_score as ss

HOLD, STEP = 252, 21

eq, jobs = ss.load()
eq = eq[eq.index >= "2013-02-01"]
rows = []
x = eq.values
for i in range(0, len(eq) - HOLD, STEP):
    with np.errstate(divide="ignore", invalid="ignore"):
        m = x[i + HOLD] / x[i]
    m = m[np.isfinite(m)]
    rows.append({"start": eq.index[i], "setups": len(m), "best": m.max(), "share_2x": (m >= 2).mean(), "share_3x": (m >= 3).mean(), "median": np.median(m)})
table = pd.DataFrame(rows)
close = ss.yf.download("AMD", start="2012-01-01", end=ss.sweep.END, auto_adjust=True, progress=False)["Close"].squeeze()
close.index = pd.DatetimeIndex(close.index).tz_localize(None).normalize()
close = close.reindex(eq.index, method="ffill").values
table["amd_held"] = [close[i + HOLD] / close[i] for i in range(0, len(eq) - HOLD, STEP)]
table.to_csv(ss.RES / "ceiling.csv", index=False)
table["year"] = table.start.dt.year
by = table.groupby("year").agg(starts=("best", "size"), any_2x=("best", lambda s: (s >= 2).mean()), any_3x=("best", lambda s: (s >= 3).mean()),
                               best=("best", "median"), setups_2x=("share_2x", "mean"), setups_3x=("share_3x", "mean"),
                               typical=("median", "median"), amd=("amd_held", "median"))
print(by.round(3).to_string())
print("all starts: some setup reached 2x", round((table.best >= 2).mean(), 3), "3x", round((table.best >= 3).mean(), 3),
      "| average setup reached 2x", round(table.share_2x.mean(), 3), "3x", round(table.share_3x.mean(), 3))
