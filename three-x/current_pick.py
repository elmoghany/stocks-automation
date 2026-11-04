"""What the walk-forward rules would select today, and what those configs would hold on the next open.

The holding is read from the rules' own signal, using Vibe-Trading's yfinance loader data via yfinance.
"""
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

import analyze2
import sweep

spec = importlib.util.spec_from_file_location("signal_template", analyze2.HERE / "signal_template.py")
rules = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rules)

eq = analyze2.load()
year = eq.index[-1].year
now, groups = len(eq) - 1, {}
for c in eq.columns:
    groups.setdefault(analyze2.group_of(c), []).append(c)
POOLS = {"pit_only": [c for c in groups["rotation"] if c.startswith("pit__")],
         "rotation_pit": groups["rotation"], "amd_pairs": groups["amd_pairs"]}
out = []
for pool, cols in POOLS.items():
    for years in (1, 2, 3, 5):
        allowed = [c for c in cols if analyze2.tradable(c, year)]
        start = eq[allowed].iloc[now - 252 * years]
        mult = (eq[allowed].iloc[now] / start).replace([np.inf, -np.inf], np.nan).dropna()
        mult = mult[start[mult.index] != eq[allowed].iloc[now][mult.index]]
        out.append({"pool": pool, "lookback_y": years, "pick": mult.idxmax(), "trailing": round(mult.max(), 2)})
table = pd.DataFrame(out)

jobs = {sweep.key(codes, cfg): (codes, cfg) for g in ("pairs", "pairs_cash", "topk") for codes, cfg in sweep.grid(g)}
symbols = sorted({c for n in table.pick for c in jobs[n][0]} | {"QQQ"})
raw = yf.download(symbols, start="2024-06-01", auto_adjust=True, progress=False)
data = {s: pd.DataFrame({"close": raw["Close"][s]}).dropna() for s in symbols}


def holding(name):
    """The name(s) with weight on the latest bar; `every` phases only change when it re-picks."""
    codes, cfg = jobs[name]
    today = {**cfg, "every": 1}
    avail = [c for c in codes if c in data]
    if "elig" in cfg:
        today["elig"] = {y: [c.replace(".US", "") for c in v] for y, v in cfg["elig"].items()}
        sig = rules._topk(data, avail, today)
    else:
        sig = rules._rotate(data, avail, today)
    return ",".join(k for k in avail if sig[k].iloc[-1] > 0) or "cash"


table["signal_now"] = table.pick.map(holding)
table.to_csv(analyze2.HERE / "results" / "current_picks.csv", index=False)
print("as of", raw.index[-1].date())
print(table.to_string(index=False))
