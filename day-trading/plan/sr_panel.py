"""Build the SWING-REVERSION daily panel from the cached grouped-daily files
(data/massive/gd, 2024-08-05 .. latest; point-in-time membership incl.
delisted names). Writes data/research_oct/sr_panel.pkl.

Split handling: the cache was fetched with adjusted=true at different times
(bulk 2026-08-03 + daily appends), so a split can appear unadjusted at its
execution date. For every Polygon split of a panel ticker inside the window
we look for the overnight jump in [E-3, E+3]; if close(t-1)/open(t) matches
the split ratio (within 0.10 in log terms; searched E-40..E+3 sessions because files were
re-fetched in blocks) the pre-jump history is rescaled
(prices * from/to, volume * to/from). Otherwise the series is already
consistent. Every split execution date is also kept so the backtests can
drop any trade whose holding window touches a split (belt and braces).
"""
import gzip
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
GD = ROOT / "data" / "massive" / "gd"
OUT = ROOT / "data" / "research_oct"

files = sorted(GD.glob("*.json.gz"))
rows = {}
for f in files:
    d = f.name[:10]
    try:
        r = json.load(gzip.open(f))
    except Exception:
        continue
    if isinstance(r, dict):
        r = r.get("results") or []
    if len(r) < 3000:  # partial / holiday file
        print("skip", d, len(r))
        continue
    rows[d] = {x["T"]: (x.get("o"), x.get("h"), x.get("l"), x.get("c"), x.get("v")) for x in r}
dates = sorted(rows)
print("days", len(dates), dates[0], dates[-1])
# candidate tickers: >= 20 days with $vol >= 5M and close >= 3, plus SPY
cnt = {}
for d in dates:
    for t, (o, h, l, c, v) in rows[d].items():
        if c and v and c >= 3 and c * v >= 5e6:
            cnt[t] = cnt.get(t, 0) + 1
tick = sorted([t for t, n in cnt.items() if n >= 20] + (["SPY"] if "SPY" not in cnt else []))
ti = {t: i for i, t in enumerate(tick)}
print("tickers", len(tick))
A = np.full((5, len(dates), len(tick)), np.nan)
for k, d in enumerate(dates):
    for t, vals in rows[d].items():
        j = ti.get(t)
        if j is not None:
            A[:, k, j] = [np.nan if v is None else v for v in vals]
P = {n: pd.DataFrame(A[i], index=pd.to_datetime(dates), columns=tick)
     for i, n in enumerate("OHLCV")}

# ---- split correction
splits = json.load(open(OUT / "splits.json"))
fix_log, split_dates = [], {}
for s in splits:
    t, E = s["ticker"], s["execution_date"]
    if t not in ti or not (dates[0] < E <= dates[-1]):
        continue
    split_dates.setdefault(t, []).append(E)
    f = s["split_from"] / s["split_to"]  # pre-split price multiplier
    if not f or f == 1:
        continue
    k = int(np.searchsorted(dates, E))
    best = None  # jump closest to the split ratio, E-40 .. E+3 sessions
    for kk in range(max(1, k - 40), min(len(dates), k + 4)):
        c0 = P["C"][t].iloc[kk - 1]
        o1 = P["O"][t].iloc[kk]
        if not (np.isfinite(c0) and np.isfinite(o1)) or c0 <= 0 or o1 <= 0:
            continue
        jump = np.log(o1 / c0)
        if best is None or abs(jump - np.log(f)) < abs(best[1] - np.log(f)):
            best = (kk, jump)
    if best is None:
        continue
    kk, jump = best
    if abs(jump - np.log(f)) < 0.10 and abs(np.log(f)) > 0.15:
        for n in "OHLC":
            P[n].iloc[:kk, P[n].columns.get_loc(t)] *= f
        P["V"].iloc[:kk, P["V"].columns.get_loc(t)] /= f
        fix_log.append((t, E, dates[kk], round(float(np.exp(jump)), 4), f))
print("split fixes", len(fix_log), fix_log[:10])
# residual huge overnight jumps (for the audit)
g = (P["O"] / P["C"].shift(1))
big = (g > 2.5) | (g < 0.35)
print("residual |gap| >150%/<-65% ticker-days:", int(big.values.sum()))
pd.to_pickle({"P": P, "split_dates": split_dates, "fix_log": fix_log}, OUT / "sr_panel.pkl")
print("saved")
