"""Scan every indicator in the `ta` library (github.com/bukosabino/ta) on AMD's real lows and highs. A study, not a trading rule.

Chosen on 2025-2026. 2024 played no part in the choice and is shown as a check. Swings of 15% or more by close; a day within 2 trading days
of a low or high counts as being at it. Separation is the area under the curve (AUC): 0.50 means the indicator looks the same at
turns as on other days, and 1.00 or 0.00 means it splits them perfectly. Indicators that change on past bars when later data
arrives are dropped, because they would peek at the future. Writes results/amd_ta_scan.csv.
"""
from pathlib import Path

import numpy as np
import pandas as pd
import ta
import yfinance as yf

RES = Path(__file__).parent / "results"
raw = yf.download("AMD", start="2022-06-01", end="2026-11-06", auto_adjust=True, progress=False)
df = pd.DataFrame({k: raw[k].squeeze() for k in ("Open", "High", "Low", "Close", "Volume")}).dropna()
df.index = pd.DatetimeIndex(df.index).tz_localize(None).normalize()
LEVELS = {"volume_adi", "volume_obv", "volume_nvi", "volume_vpt", "others_cr"}  # running totals, whose level has no meaning across years


def features(frame):
    out = ta.add_all_ta_features(frame.copy(), open="Open", high="High", low="Low", close="Close", volume="Volume", fillna=False)
    return out.drop(columns=["Open", "High", "Low", "Close", "Volume"]).replace([np.inf, -np.inf], np.nan)


full = features(df)
peek = set()
for cut in ("2024-06-28", "2025-06-30", "2026-03-31"):
    part = features(df.loc[:cut])
    last_full, last_part = full.loc[part.index[-1]], part.iloc[-1]
    diff = (last_full - last_part).abs() > 1e-6 * (1 + last_full.abs())
    peek |= set(diff.index[diff.values])
print("indicators", full.shape[1], "| change when later data arrives:", sorted(peek))
keep = [c for c in full.columns if c not in peek and c not in LEVELS and full[c].nunique() > 5]
print("kept", len(keep))


def swings(close, threshold=0.15):
    v = close.values
    lows, highs, hi, lo, way = [], [], 0, 0, 0
    for i in range(1, len(v)):
        if v[i] > v[hi]:
            hi = i
        if v[i] < v[lo]:
            lo = i
        if way >= 0 and v[i] <= v[hi] * (1 - threshold):
            highs.append(hi)
            way, lo = -1, i
        elif way <= 0 and v[i] >= v[lo] * (1 + threshold):
            lows.append(lo)
            way, hi = 1, i
    return lows, highs


def labels(index, points):
    y = np.zeros(len(index), dtype=bool)
    for p in points:
        y[max(0, p - 2):p + 3] = True
    return y


def auc(x, y):
    ok = np.isfinite(x)
    x, y = x[ok], y[ok]
    if y.sum() == 0 or (~y).sum() == 0:
        return np.nan
    ranks = pd.Series(x).rank().values
    return (ranks[y].sum() - y.sum() * (y.sum() + 1) / 2) / (y.sum() * (~y).sum())


rows = []
eras = {"2025-26": ("2025-01-01", "2026-11-06"), "2024": ("2024-01-01", "2024-12-31")}
for era, (a, b) in eras.items():
    close = df.Close.loc[a:b]
    lows, highs = swings(close)
    print(era, "lows", [str(close.index[i].date()) for i in lows], "highs", [str(close.index[i].date()) for i in highs])
    ylow, yhigh = labels(close.index, lows), labels(close.index, highs)
    for c in keep:
        x = full[c].loc[a:b].values
        rows.append({"indicator": c, "era": era, "auc_low": auc(x, ylow), "auc_high": auc(x, yhigh), "at_lows": np.nanmedian(x[ylow]), "at_highs": np.nanmedian(x[yhigh]), "all_days": np.nanmedian(x)})
t = pd.DataFrame(rows)
wide = t.pivot(index="indicator", columns="era", values=["auc_low", "auc_high", "at_lows", "at_highs", "all_days"])
wide.columns = [f"{a}_{b}" for a, b in wide.columns]
wide = wide.reset_index()
wide["low_power"] = (wide["auc_low_2025-26"] - 0.5).abs()
wide["high_power"] = (wide["auc_high_2025-26"] - 0.5).abs()
wide["both"] = wide[["low_power", "high_power"]].min(axis=1)
wide.to_csv(RES / "amd_ta_scan.csv", index=False)
pd.set_option("display.width", 200, "display.max_columns", 20, "display.max_rows", 60)
fmt = lambda v: f"{v:.2f}"
for title, sort, cols in (("LOWS: best on 2025-26", "low_power", ["indicator", "auc_low_2025-26", "auc_low_2024", "at_lows_2025-26", "all_days_2025-26"]),
                          ("HIGHS: best on 2025-26", "high_power", ["indicator", "auc_high_2025-26", "auc_high_2024", "at_highs_2025-26", "all_days_2025-26"]),
                          ("BOTH: separates lows and highs", "both", ["indicator", "auc_low_2025-26", "auc_low_2024", "auc_high_2025-26", "auc_high_2024", "at_lows_2025-26", "at_highs_2025-26", "all_days_2025-26"])):
    print(f"\n{title}")
    print(wide.sort_values(sort, ascending=False).head(15)[cols].to_string(index=False, float_format=fmt))
