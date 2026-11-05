"""How does an AMD quarter usually behave? All complete quarters stretched onto one timeline by interpolation. No trading rule.

Each quarter runs from one report-day close to the next and is resampled to 0-100% of the quarter by linear interpolation. "Level" is
price against the starting close. "Shape" removes each quarter's straight line from start to end, which shows timing whether
the quarter rose or fell. To test whether the shape is real, each quarter is compared with the typical shape of the others,
then the same is done for quarter-length stretches starting at random dates. Today's quarter is compared with history.

Writes results/amd_typical_quarter.csv.
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
reports = sorted({int(idx.searchsorted(d)) for d in dates if pd.Timestamp("2023-07-15") <= d <= idx[-1]})
GRID = np.arange(0, 101)


def stretch(a, b):
    """Level path from bar a to bar b, on the 0-100% grid."""
    y = c[a:b + 1] / c[a]
    return np.interp(GRID / 100 * (b - a), np.arange(b - a + 1), y)


def shape_of(path):
    return path - (1 + (path[-1] - 1) * GRID / 100)


def fit(paths):
    """Average correlation of each path's shape with the median shape of the others."""
    shapes = np.array([shape_of(p) for p in paths])
    out = []
    for i in range(len(shapes)):
        rest = np.median(np.delete(shapes, i, axis=0), axis=0)
        out.append(np.corrcoef(shapes[i], rest)[0, 1])
    return np.array(out)


pairs = list(zip(reports[:-1], reports[1:]))
labels = [idx[a].strftime("%b %Y") for a, _ in pairs]
paths = np.array([stretch(a, b) for a, b in pairs])
shapes = np.array([shape_of(p) for p in paths])
median_len = int(np.median([b - a for a, b in pairs]))
table = pd.DataFrame({"pct": GRID, "trading_day": np.round(GRID / 100 * median_len, 1), "median": np.median(paths, axis=0) - 1, "p25": np.percentile(paths, 25, axis=0) - 1,
                      "p75": np.percentile(paths, 75, axis=0) - 1, "worst": paths.min(axis=0) - 1, "best": paths.max(axis=0) - 1, "above_start": (paths > 1).mean(axis=0), "shape": np.median(shapes, axis=0)})
table.to_csv(RES / "amd_typical_quarter.csv", index=False)
print(f"{len(paths)} complete quarters, typical length {median_len} trading days, from {labels[0]} to {labels[-1]}")
print("\nday  median     middle half       worst    best   above start   shape")
for pct in range(0, 101, 5):
    r = table.iloc[pct]
    print(f"{r.trading_day:4.0f} {r['median']:+7.1%}  {r.p25:+7.1%} {r.p75:+7.1%}  {r.worst:+7.1%} {r.best:+7.1%}   {int(round(r.above_start * len(paths))):2d} of {len(paths)}  {r['shape']:+7.1%}")
s = table["shape"].values
print(f"\ntypical shape low {s.min():+.1%} at day {table.trading_day[s.argmin()]:.0f}; high {s.max():+.1%} at day {table.trading_day[s.argmax()]:.0f}")
m = table["median"].values
print(f"median level low {m.min():+.1%} at day {table.trading_day[m.argmin()]:.0f}; high {m.max():+.1%} at day {table.trading_day[m.argmax()]:.0f}; end {m[-1]:+.1%}")

real = fit(paths)
print("\nhow well each quarter fits the typical shape of the others (correlation)")
print("  " + ", ".join(f"{a} {b:+.2f}" for a, b in zip(labels, real)))
print(f"  average {real.mean():+.2f}; positive in {(real > 0).sum()} of {len(real)}")
rng = np.random.default_rng(11)
lengths = [b - a for a, b in pairs]
first, last = reports[0], reports[-1]
fake = []
for _ in range(2000):
    fp = []
    for length in lengths:
        a = int(rng.integers(first, last - length))
        fp.append(stretch(a, a + length))
    fake.append(fit(np.array(fp)).mean())
fake = np.array(fake)
print(f"  random stretches: average {fake.mean():+.2f}, 95th percentile {np.percentile(fake, 95):+.2f}; share at or above the real {real.mean():+.2f}: {(fake >= real.mean()).mean():.1%}")

r = reports[-1]
days = len(c) - 1 - r
at = np.array([c[a + days] / c[a] - 1 for a, _ in pairs])
rest = np.array([c[b] / c[a + days] - 1 for a, b in pairs])
print(f"\ncurrent quarter: report {idx[r].date()} {c[r]:.2f}, day {days}, close {c[-1]:.2f} ({c[-1] / c[r] - 1:+.1%})")
print(f"at day {days} in past quarters: median {np.median(at):+.1%}, range {at.min():+.1%} to {at.max():+.1%}; at or below today in {(at <= c[-1] / c[r] - 1).sum()} of {len(at)}")
print(f"from day {days} to the next report: median {np.median(rest):+.1%}, middle half {np.percentile(rest, 25):+.1%} to {np.percentile(rest, 75):+.1%}, range {rest.min():+.1%} to {rest.max():+.1%}; up in {(rest > 0).sum()} of {len(rest)}")
for name, a0, v, w in zip(labels, [a for a, _ in pairs], at, rest):
    print(f"  {name}: day {days} {v:+.1%}, then {w:+.1%}")
