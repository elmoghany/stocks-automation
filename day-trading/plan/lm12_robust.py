"""LEGACY-12 part 3: tail-robustness of the bucket findings.  R4 is carried by
5 legs (CHAMPION-REPLAY), so every bucket is re-read with (a) per-leg gross
winsorised at +/-$500 per $10k ticket (+/-5%), (b) the R4 top-5 legs removed,
(c) median leg.  Same for the 30 random seeds (pooled) and C37F-hf3.
"""
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lm12_buckets as B  # noqa: E402

TK, Y1, W = 10_000.0, "2025-08-01", 500.0
r4, ndays = B.load_r4()
hf3 = B.load_hf3()
allsets = dict(r4)
allsets["HF3"] = hf3
keys = sorted({(r["date"], r["sym"]) for rows in allsets.values() for r in rows})
cache = {(s, d): B.feats(s, d, None) for d, s in keys}
for rows in allsets.values():
    for r in rows:
        r["f"] = dict(cache[(r["sym"], r["date"])], price=r["entry"])
cm = defaultdict(list)
for k, v in r4.items():
    for r in v:
        cm[B.bucket("dvol60", r["f"]["dvol60"])].append(r["bps"])
cmd = {k: float(np.mean(v)) for k, v in cm.items()}
for r in hf3:
    r["bps"] = cmd.get(B.bucket("dvol60", r["f"]["dvol60"]), 28.75)
top5 = set(id(r) for r in sorted(r4["R4"], key=lambda r: -r["ret"])[:5])
print("R4 top5:", [(r["date"], r["sym"], round(r["ret"] * TK), B.bucket("price", r["entry"]),
                    B.bucket("dvol60", r["f"]["dvol60"]), r["f"]["rvol1"] and round(r["f"]["rvol1"], 2))
                   for r in r4["R4"] if id(r) in top5])
rnd = [r for k, v in r4.items() if k.startswith("RND") for r in v]


def line(rows, ex5=False):
    rows = [r for r in rows if not (ex5 and id(r) in top5)]
    if not rows:
        return "n=0"
    g = np.array([r["ret"] * TK for r in rows])
    w = np.clip(g, -W, W)
    y1 = np.array([r["date"] < Y1 for r in rows])
    wc = w - 2 * TK * 0.65 * np.array([r.get("bps") or 28.75 for r in rows]) / 1e4
    f = lambda a, m: f"{a[m].mean():+6.1f}" if m.any() else "   nan"
    return (f"n={len(rows):5d} wins {f(w, y1 | ~y1)} (Y1 {f(w, y1)} Y2 {f(w, ~y1)}) med {np.median(g):+6.1f} "
            f"| wins-net@central {f(wc, y1 | ~y1)} (Y1 {f(wc, y1)} Y2 {f(wc, ~y1)})")


for k in ("price", "dvol60", "rvol1", "pdv", "mcap"):
    print(f"\n== {k} ==")
    for b in sorted({B.bucket(k, r["f"][k]) for r in r4["R4"] + hf3}):
        sel = lambda rows: [r for r in rows if B.bucket(k, r["f"][k]) == b]
        print(f"{b:>14} R4ex5 {line(sel(r4['R4']), True)}")
        print(f"{'':>14} RND   {line(sel(rnd))}")
        print(f"{'':>14} HF3   {line(sel(hf3))}")
