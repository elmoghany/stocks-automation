"""AMD's cycle around earnings over the last 3 years, in weeks (user order 2026-11-05: weekly or monthly trading only).

The user's pattern: a dip before the report, a rise just before it, a large drop after it, then a recovery. D is the report
date. AMD normally reports after the close, so the reaction is D+1; the script checks that. Each step is compared with
ordinary AMD days: the same number of days starting on any date in the window, so AMD's rise is not mistaken for a pattern.

About 12 reports fit in the window, so these numbers can suggest a pattern but cannot establish one.
Writes results/amd_cycle_events.csv and results/amd_cycle_steps.csv.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

RES = Path(__file__).parent / "results"
START, END = "2023-11-05", "2026-11-05"
# name: (from, to), in trading days relative to the report date D; 5 trading days is one week
STEPS = {"dip: 4 weeks before to 1 week before": (-20, -5), "rise: last week before": (-5, 0), "reaction: the day after": (0, 1),
         "drop: first 2 weeks after": (1, 10), "recovery: weeks 3 to 8 after": (10, 40)}
SIGNS = dict(zip(STEPS, (-1, 1, -1, -1, 1)))

raw = yf.download("AMD", start="2023-06-01", end=END, auto_adjust=True, progress=False)
close = raw["Close"].squeeze().dropna()
close.index = pd.DatetimeIndex(close.index).tz_localize(None).normalize()
c, idx = close.values, close.index
window = np.nonzero(idx >= START)[0]
print(f"AMD held {idx[window[0]].date()} to {idx[-1].date()}: {c[-1] / c[window[0]]:.2f}x, worst fall from a high {np.min(c[window] / np.maximum.accumulate(c[window]) - 1):.0%}")
dates = pd.to_datetime(json.loads((RES / "earnings_dates.json").read_text(encoding="utf-8"))["AMD"])
pos = sorted({int(idx.searchsorted(d)) for d in dates if pd.Timestamp(START) <= d <= idx[-1]})
print("reports", len(pos), [str(idx[p].date()) for p in pos])

moves = [(abs(c[p] / c[p - 1] - 1), abs(c[p + 1] / c[p] - 1)) for p in pos if p + 1 < len(c)]
print(f"reaction timing: the day after is the bigger move in {np.mean([b > a for a, b in moves]):.0%} of reports; median move {np.median([b for _, b in moves]):.1%}, ordinary day {np.median(np.abs(np.diff(c[window]) / c[window][:-1])):.1%}")

rows = []
for p in pos:
    row = {"date": idx[p].date()}
    for name, (a, b) in STEPS.items():
        row[name] = c[p + b] / c[p + a] - 1 if p + b < len(c) else np.nan
    if p + 5 < len(c):
        span = c[p + 1:min(p + 21, len(c))]
        row["lowest within 4 weeks"], row["weeks to low"] = span.min() / c[p] - 1, (int(span.argmin()) + 1) / 5
        after = np.nonzero(c[p + 1:p + 64] >= c[p])[0]
        row["weeks to regain"] = (after[0] + 1) / 5 if len(after) else np.nan
    rows.append(row)
ev = pd.DataFrame(rows)
ev.to_csv(RES / "amd_cycle_events.csv", index=False)
pd.set_option("display.width", 220, "display.max_columns", 20, "display.max_rows", 100, "display.max_colwidth", 40)
print(ev.rename(columns={k: k.split(":")[0] for k in STEPS}).to_string(index=False, float_format=lambda v: f"{v:+.2f}"))

rng = np.random.default_rng(7)
out = []
for name, (a, b) in STEPS.items():
    v = ev[name].dropna().values
    length = b - a
    starts = window[window + length < len(c)]
    ordinary = c[starts + length] / c[starts] - 1
    draws = rng.choice(ordinary, size=(20000, len(v))).mean(axis=1)
    out.append({"step": name, "reports": len(v), "avg": v.mean(), "median": np.median(v), "up": (v > 0).mean(), "ordinary_avg": ordinary.mean(),
                "ordinary_up": (ordinary > 0).mean(), "chance_p": np.mean(np.abs(draws - ordinary.mean()) >= abs(v.mean() - ordinary.mean()))})
table = pd.DataFrame(out)
table.to_csv(RES / "amd_cycle_steps.csv", index=False)
print()
print(table.to_string(index=False, float_format=lambda v: f"{v:.3f}"))

steps = list(STEPS)
done = ev.dropna(subset=steps)
hit = np.all([np.sign(done[s]) == SIGNS[s] for s in steps], axis=0)
print(f"\nall five steps in the expected direction: {hit.sum()} of {len(done)} reports; expected if the steps were unrelated: {np.prod([(np.sign(done[s]) == SIGNS[s]).mean() for s in steps]) * len(done):.1f}")
low = ev["lowest within 4 weeks"].dropna()
print(f"after the report, within 4 weeks: median low {low.median():.1%}; fell 5%+ in {(low <= -.05).sum()}, 10%+ in {(low <= -.10).sum()}, 20%+ in {(low <= -.20).sum()} of {len(low)}")
