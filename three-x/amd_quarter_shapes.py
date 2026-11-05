"""What AMD did in each earnings quarter, from one report to the next. A description only, with no trading rule.

Closes only. Day numbers are trading days after the report. "Low" is the quarter's lowest close after the report and "high" is
the highest close after that low, so the steps run in order. Writes results/amd_quarter_shapes.csv.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

RES = Path(__file__).parent / "results"
raw = yf.download("AMD", start="2023-06-01", end="2026-11-06", auto_adjust=True, progress=False)
close = raw["Close"].squeeze().dropna()
close.index = pd.DatetimeIndex(close.index).tz_localize(None).normalize()
c, idx = close.values, close.index
dates = pd.to_datetime(json.loads((RES / "earnings_dates.json").read_text(encoding="utf-8"))["AMD"])
reports = sorted({int(idx.searchsorted(d)) for d in dates if pd.Timestamp("2023-10-01") <= d <= idx[-1]})

rows = []
for j, r in enumerate(reports):
    end = reports[j + 1] if j + 1 < len(reports) else len(c) - 1
    if end <= r:
        continue
    span = c[r + 1:end + 1]
    low = r + 1 + int(np.argmin(span))
    high = low + int(np.argmax(c[low:end + 1]))
    rows.append({"report": idx[r].date(), "close": round(c[r], 2), "next_day": c[r + 1] / c[r] - 1, "days": end - r, "low_day": low - r, "low_date": idx[low].date(), "low_vs_report": c[low] / c[r] - 1,
                 "high_day": high - r, "high_date": idx[high].date(), "rise_low_to_high": c[high] / c[low] - 1, "days_before_next": end - high, "fall_high_to_end": c[end] / c[high] - 1,
                 "quarter": c[end] / c[r] - 1, "complete": j + 1 < len(reports)})
table = pd.DataFrame(rows)
table.to_csv(RES / "amd_quarter_shapes.csv", index=False)
pd.set_option("display.width", 220, "display.max_columns", 20)
print(table.to_string(index=False, float_format=lambda v: f"{v:+.2f}"))
done = table[table.complete]
print(f"\ncomplete quarters {len(done)}: up {(done.quarter > 0).sum()}, median {done.quarter.median():+.1%}, low day median {done.low_day.median():.0f}, high day median {done.high_day.median():.0f}, rise median {done.rise_low_to_high.median():+.0%}, fall into next report median {done.fall_high_to_end.median():+.0%}")
season = pd.to_datetime(done.report).dt.month.map(lambda m: "Jan/Feb" if m in (1, 2) else "Apr/May" if m in (4, 5) else "Jul/Aug" if m in (7, 8) else "Oct/Nov")
print(done.groupby(season).agg(n=("quarter", "size"), quarter=("quarter", "median"), next_day=("next_day", "median"), low_vs=("low_vs_report", "median"), low_day=("low_day", "median"), rise=("rise_low_to_high", "median"), high_day=("high_day", "median")).round(2).to_string())
