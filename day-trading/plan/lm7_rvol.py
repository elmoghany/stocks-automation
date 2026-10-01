"""LEGACY-7: robustness of the two all-cells vetoes (low session rvol,
extreme Amihud) -- threshold grid, time-of-day confound, overlap."""
import pickle
import sys
from pathlib import Path

import numpy as np

T = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
    r"C:/Users/MYPC~1/AppData/Local/Temp/claude/C--cornell-stocks-automation/"
    r"20a29bc8-aa0d-497e-a600-4db3499b8240/scratchpad/lm7_table.pkl")
rows = pickle.load(open(T, "rb"))
CELLS = [(s, y) for s in ("R4", "C37F") for y in (1, 2)]
# expected cumulative fraction of the day's $ volume by minute-of-day, a
# FIXED prior (U-shape, ~10% in first 5 min, ~35% by 10:30) -- not fitted.
def frac(mod):
    mod = max(1.0, mod)
    return min(1.0, 0.10 * (mod / 5.0) ** 0.5) if mod <= 60 else min(1.0, 0.35 + 0.65 * (mod - 60) / 330)


for r in rows:
    r["rvol_tn"] = r["rvol_now"] / frac(r["min_of_day"]) if np.isfinite(r["rvol_now"]) else np.nan


def line(name, f):
    out = [f"{name:34s}"]
    tot_sv = 0
    for s, y in CELLS:
        rs = [r for r in rows if r["strat"] == s and r["y"] == y]
        g = np.array([r["g10k"] for r in rs])
        m = np.array([bool(f(r)) for r in rs])
        sv = -g[m].sum()
        tot_sv += sv
        out.append(f"{s}Y{y} n{m.sum():3d} {(g[m].mean() if m.any() else 0):+6.0f} sv{sv:+7.0f}")
    print(" | ".join(out), f"| total sv {tot_sv:+.0f}")


nan = lambda v: v if np.isfinite(v) else np.inf   # noqa: E731
print("rvol_now thresholds")
for th in (0.03, 0.05, 0.07, 0.10, 0.15, 0.20, 0.30):
    line(f"rvol_now<{th}", lambda r, th=th: nan(r["rvol_now"]) < th)
print("time-normalised rvol (fixed U-shape prior)")
for th in (0.1, 0.2, 0.3, 0.5, 0.75):
    line(f"rvol_tn<{th}", lambda r, th=th: nan(r["rvol_tn"]) < th)
print("amihud thresholds (bps per $1M)")
for th in (5e4, 1e5, 1.5e5, 2.5e5, 4e5):
    line(f"amihud>{th:.0e}", lambda r, th=th: r["amihud"] > th)
print("dvol60 (prior 60d avg $vol) thresholds")
for th in (2e5, 5e5, 1e6):
    line(f"dvol60<{th:.0e}", lambda r, th=th: nan(r["dvol60"]) < th)
line("rvol07 OR amihud>2.5e5", lambda r: nan(r["rvol_now"]) < 0.07 or r["amihud"] > 2.5e5)
line("rvol07 AND amihud>2.5e5", lambda r: nan(r["rvol_now"]) < 0.07 and r["amihud"] > 2.5e5)
line("rvol_now NaN (no dvol60)", lambda r: not np.isfinite(r["rvol_now"]))
print("\nminute-of-day of rvol<0.07 vetoes vs all:")
for s in ("R4", "C37F"):
    rs = [r for r in rows if r["strat"] == s]
    v = [r["min_of_day"] for r in rs if nan(r["rvol_now"]) < 0.07]
    a = [r["min_of_day"] for r in rs]
    print(s, "veto median mod", np.median(v), "all", np.median(a),
          "veto median dvol60", np.median([r["dvol60"] for r in rs if nan(r["rvol_now"]) < 0.07]),
          "all", np.nanmedian([r["dvol60"] for r in rs]))
print("\nworst-decile coverage of the OR veto:")
for s in ("R4", "C37F"):
    rs = [r for r in rows if r["strat"] == s]
    g = np.array([r["g10k"] for r in rs])
    lo, hi = np.percentile(g, 10), np.percentile(g, 90)
    m = np.array([nan(r["rvol_now"]) < 0.07 or r["amihud"] > 2.5e5 for r in rs])
    print(s, f"vetoed {m.sum()} of {len(rs)}; worst10% hit {(m & (g <= lo)).sum()}/{(g <= lo).sum()} "
          f"(${-g[m & (g <= lo)].sum():.0f} saved); best10% hit {(m & (g >= hi)).sum()} "
          f"(${g[m & (g >= hi)].sum():.0f} forgone); middle {(m & (g > lo) & (g < hi)).sum()} "
          f"(${g[m & (g > lo) & (g < hi)].sum():+.0f})")
print("\nexit reasons of the OR-vetoed legs:")
for s in ("R4", "C37F"):
    d = {}
    for r in rows:
        if r["strat"] == s and (nan(r["rvol_now"]) < 0.07 or r["amihud"] > 2.5e5):
            d.setdefault(r["reason"], []).append(r["g10k"])
    print(s, {k: (len(v), round(float(np.mean(v)))) for k, v in d.items()})
