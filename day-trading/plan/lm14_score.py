"""LEGACY-14 scorer: per-job $ at $10k tickets, gross and net at per-side
bps, Y1/Y2, ex-top-5 legs, and a PAIRED day-level delta vs R4 (t-stat).
Usage: python lm14_score.py legs.json [base=R4]"""
import json
import sys
from collections import defaultdict

import numpy as np

d = json.load(open(sys.argv[1]))
base = sys.argv[2] if len(sys.argv) > 2 else "R4"
J = d["legs"]
Y2 = "2025-08-01"
NM = 22
NM1, NM2 = 10, 12


def net(x, b):
    return x["gross"] - b / 1e4 * (x["entry"] + x["exit"]) * x["shares"]


def byday(L, b):
    o = defaultdict(float)
    for x in L:
        o[x["date"]] += net(x, b)
    return o


alldays = sorted({x["date"] for L in J.values() for x in L})
bd15 = byday(J[base], 15)
print("| config | tkts | tkt/day | $/tkt gross | $/tkt 6bps | $/tkt 15bps | $/mo gross | "
      "$/mo 15bps | Y1 / Y2 $/mo 15bps | months+ 15 | ex-top5 $/mo 15 | "
      "delta $/mo vs R4 @15 | paired-day t | delta Y1 / Y2 |")
print("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
for k, L in J.items():
    if k == "R4_15k":
        continue
    n = len(L)
    g = sum(x["gross"] for x in L)
    v6 = sum(net(x, 6) for x in L)
    v15 = [net(x, 15) for x in L]
    t15 = sum(v15)
    y1 = sum(net(x, 15) for x in L if x["date"] < Y2)
    y2 = t15 - y1
    mon = defaultdict(float)
    for x in L:
        mon[x["date"][:7]] += net(x, 15)
    mp = sum(1 for v in mon.values() if v > 0)
    ex5 = sum(sorted(v15, reverse=True)[5:])
    b = byday(L, 15)
    diff = np.array([b.get(dd, 0.0) - bd15.get(dd, 0.0) for dd in alldays])
    tt = diff.mean() / (diff.std(ddof=1) / np.sqrt(len(diff))) if diff.std() > 0 else 0.0
    d1 = sum(v for dd, v in zip(alldays, diff) if dd < Y2) / NM1
    d2 = sum(v for dd, v in zip(alldays, diff) if dd >= Y2) / NM2
    print(f"| {k} | {n} | {n/d['ndays']:.2f} | {g/n:+.1f} | {v6/n:+.1f} | {t15/n:+.1f} | "
          f"{g/NM:+,.0f} | {t15/NM:+,.0f} | {y1/NM1:+,.0f} / {y2/NM2:+,.0f} | {mp}/{len(mon)} | "
          f"{ex5/NM:+,.0f} | {diff.sum()/NM:+,.0f} | {tt:+.2f} | {d1:+,.0f} / {d2:+,.0f} |")
