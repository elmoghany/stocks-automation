"""The exact path of AMD in each earnings quarter: every swing of 10% or more between two reports, by closing price.

A description only, with no trading rule. Writes results/amd_quarter_paths.csv.
"""
import json
from pathlib import Path

import pandas as pd
import yfinance as yf

RES = Path(__file__).parent / "results"
SWING = 0.10
raw = yf.download("AMD", start="2023-06-01", end="2026-11-06", auto_adjust=True, progress=False)
close = raw["Close"].squeeze().dropna()
close.index = pd.DatetimeIndex(close.index).tz_localize(None).normalize()
c, idx = close.values, close.index
dates = pd.to_datetime(json.loads((RES / "earnings_dates.json").read_text(encoding="utf-8"))["AMD"])
reports = sorted({int(idx.searchsorted(d)) for d in dates if pd.Timestamp("2023-10-01") <= d <= idx[-1]})


def path(a, b):
    """Turning points from bar a to bar b, each confirmed by a reversal of SWING before b, plus both ends."""
    points, hi, lo, way = [a], a, a, 0
    for i in range(a + 1, b + 1):
        if c[i] > c[hi]:
            hi = i
        if c[i] < c[lo]:
            lo = i
        if way >= 0 and c[i] <= c[hi] * (1 - SWING):
            if hi != points[-1]:
                points.append(hi)
            way, lo = -1, i
        elif way <= 0 and c[i] >= c[lo] * (1 + SWING):
            if lo != points[-1]:
                points.append(lo)
            way, hi = 1, i
    if b != points[-1]:
        points.append(b)
    return points


rows = []
for j, r in enumerate(reports):
    end = reports[j + 1] if j + 1 < len(reports) else len(c) - 1
    points = path(r, end)
    print(f"\nReport {idx[r].date()} close {c[r]:.2f}; next day {idx[r + 1].date()} {c[r + 1]:.2f} ({c[r + 1] / c[r] - 1:+.1%}); {'to next report' if j + 1 < len(reports) else 'to today'} {idx[end].date()} {c[end]:.2f} ({c[end] / c[r] - 1:+.1%})")
    for x, y in zip(points[:-1], points[1:]):
        print(f"  {idx[x].date()} {c[x]:.2f} -> {idx[y].date()} {c[y]:.2f}: {c[y] / c[x] - 1:+.1%}, day {x - r} to {y - r}")
        rows.append({"report": idx[r].date(), "from": idx[x].date(), "from_close": round(c[x], 2), "to": idx[y].date(), "to_close": round(c[y], 2), "move": c[y] / c[x] - 1, "from_day": x - r, "to_day": y - r})
pd.DataFrame(rows).to_csv(RES / "amd_quarter_paths.csv", index=False)
