"""Pattern 5 as it unfolds: compare a quarter so far with a typical path for each shape. No trading rule here.

Shapes are labels given after each quarter ended, from AMD_QUARTERS.md. Typical paths are interpolated medians of each shape's quarters.
Tests at each check day:
  leave-one-out: judge each quarter against typical paths built from the other 12, which uses later quarters too.
  walk-forward: judge each quarter using only quarters already finished, which could have been done at the time.
Both report whether the shape was right, and whether predicted good shapes (up, fall then rise) went on to do better than predicted
bad shapes (fade, down) from the check day to the next report. Shuffled labels show what chance gives.

Writes results/amd_shape_templates.csv, results/amd_shape_tests.csv and results/amd_shape_blocks.json.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

RES = Path(__file__).parent / "results"
SHAPES = {"up": ["Oct 2023", "May 2025", "May 2026"], "fall_then_rise": ["Jul 2024", "Aug 2025", "Nov 2025", "Feb 2026"],
          "fade": ["Jan 2024", "Apr 2024", "Aug 2026"], "down": ["Aug 2023", "Oct 2024", "Feb 2025"]}
GOOD = {"up", "fall_then_rise"}
CHECKS = (5, 10, 15, 20, 30, 40)
BLOCK_DAY = 20  # set before any test: the typical low comes around days 21-26
raw = yf.download("AMD", start="2023-06-01", end="2026-11-06", auto_adjust=True, progress=False)
close = raw["Close"].squeeze().dropna()
close.index = pd.DatetimeIndex(close.index).tz_localize(None).normalize()
c, idx = close.values, close.index
dates = pd.to_datetime(json.loads((RES / "earnings_dates.json").read_text(encoding="utf-8"))["AMD"])
reports = sorted({int(idx.searchsorted(d)) for d in dates if pd.Timestamp("2023-07-15") <= d <= idx[-1]})
pairs = list(zip(reports[:-1], reports[1:]))
names = [idx[a].strftime("%b %Y") for a, _ in pairs]
shape_of = {n: s for s, members in SHAPES.items() for n in members}
labels = np.array([shape_of[n] for n in names])
paths = [c[a:b + 1] / c[a] - 1 for a, b in pairs]
rng = np.random.default_rng(5)


def judge(path, d, pool, pool_labels):
    best, score = None, np.inf
    for shape in sorted(set(pool_labels)):
        members = np.array([paths[j][:d + 1] for j, lab in zip(pool, pool_labels) if lab == shape])
        rms = np.sqrt(np.mean((path[:d + 1] - np.median(members, axis=0)) ** 2))
        if rms < score:
            best, score = shape, rms
    return best


def run(lab, d):
    out = []
    for i in range(len(paths)):
        pool = [j for j in range(len(paths)) if j != i]
        out.append(judge(paths[i], d, pool, lab[pool]))
    return np.array(out)


def gap(pred, rest):
    good = np.array([p in GOOD for p in pred])
    return rest[good].mean() - rest[~good].mean() if good.any() and (~good).any() else np.nan


grid = np.arange(0, 101)
template_rows = []
for shape, members in SHAPES.items():
    stretched = [np.interp(grid / 100 * (len(paths[names.index(m)]) - 1), np.arange(len(paths[names.index(m)])), paths[names.index(m)]) for m in members]
    median = np.median(stretched, axis=0)
    template_rows.append(pd.Series(median, index=grid, name=shape))
templates = pd.DataFrame(template_rows).T
templates.to_csv(RES / "amd_shape_templates.csv", index_label="pct_of_quarter")
print("typical path of each shape, interpolated (about 63 trading days)")
print("day    " + "".join(f"{s:>16s}" for s in SHAPES))
for pct in range(0, 101, 10):
    print(f"{pct * 0.63:4.0f}   " + "".join(f"{templates.loc[pct, s]:+16.1%}" for s in SHAPES))

rows = []
print("\nleave-one-out, then walk-forward, at each check day")
for d in CHECKS:
    rest = np.array([c[b] / c[a + d] - 1 for a, b in pairs])
    pred = run(labels, d)
    right = (pred == labels).mean()
    diff = gap(pred, rest)
    chance_right, chance_gap = [], []
    for _ in range(1000):
        s = rng.permutation(labels)
        p2 = run(s, d)
        chance_right.append((p2 == s).mean())
        chance_gap.append(gap(p2, rest))
    chance_right, chance_gap = np.array(chance_right), np.array(chance_gap)
    wf, wf_rest = [], []
    for i in range(len(paths)):
        pool = list(range(i))
        if len(set(labels[pool])) >= 2:
            wf.append((judge(paths[i], d, pool, labels[pool]), labels[i]))
            wf_rest.append(rest[i])
    wf_pred = np.array([w[0] for w in wf])
    wf_true = np.array([w[1] for w in wf])
    wf_rest = np.array(wf_rest)
    good = np.array([p in GOOD for p in wf_pred])
    row = {"day": d, "loo_right": right, "chance_right": chance_right.mean(), "p_right": (chance_right >= right).mean(), "loo_gap": diff, "p_gap": np.nanmean(chance_gap >= diff),
           "wf_n": len(wf), "wf_right": (wf_pred == wf_true).mean(), "wf_good_n": int(good.sum()), "wf_good": wf_rest[good].mean() if good.any() else np.nan,
           "wf_bad_n": int((~good).sum()), "wf_bad": wf_rest[~good].mean() if (~good).any() else np.nan}
    rows.append(row)
    print(f"day {d:2d}: shape right {right:.0%} (chance {chance_right.mean():.0%}, p {row['p_right']:.2f}); good minus bad afterward {diff:+.0%} (p {row['p_gap']:.2f}) | walk-forward {row['wf_n']} quarters: right {row['wf_right']:.0%}; rest of quarter when judged good {row['wf_good']:+.0%} ({row['wf_good_n']}), bad {row['wf_bad']:+.0%} ({row['wf_bad_n']})")
pd.DataFrame(rows).to_csv(RES / "amd_shape_tests.csv", index=False)

print(f"\nwalk-forward at day {BLOCK_DAY}, quarter by quarter")
blocks = []
for i, (a, b) in enumerate(pairs):
    pool = list(range(i))
    if len(set(labels[pool])) < 2:
        print(f"  {names[i]}: too little history, actual {labels[i]}")
        continue
    p = judge(paths[i], BLOCK_DAY, pool, labels[pool])
    rest = c[b] / c[a + BLOCK_DAY] - 1
    print(f"  {names[i]}: judged {p}, actual {labels[i]}, rest of quarter {rest:+.1%}")
    if p not in GOOD:
        blocks.append({"from": str(idx[a + BLOCK_DAY].date()), "to": str(idx[b].date())})
(RES / "amd_shape_blocks.json").write_text(json.dumps(blocks, indent=1), encoding="utf-8")

r = reports[-1]
d = len(c) - 1 - r
now = c[r:] / c[r] - 1
print(f"\ncurrent quarter: {idx[r].date()} {c[r]:.2f}, day {d}, close {c[-1]:.2f} ({now[-1]:+.1%})")
for shape, members in SHAPES.items():
    t = np.median([paths[names.index(m)][:d + 1] for m in members], axis=0)
    print(f"  distance from {shape}: {np.sqrt(np.mean((now - t) ** 2)):.1%}; that shape at this day {t[-1]:+.1%}")
