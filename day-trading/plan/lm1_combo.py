"""LEGACY-1: combined exit stacks on fixed entries (R4, RND0-4, HF3)."""
import json, sys, collections
import numpy as np
sys.path.insert(0, r"C:\cornell\stocks-automation\day-trading\plan")
import cp_lib as L
from lm1_walk import V, walk
B = r"C:\cornell\stocks-automation\day-trading"
VAR = {"base_next": V(fill="next"), "stop8_close": V(stop=0.08),
       "bm1": V(bear_min=0.01, fill="next"),
       "bm1_tp10": V(bear_min=0.01, tp=0.10, fill="next"),
       "bm1_tp15": V(bear_min=0.01, tp=0.15, fill="next"),
       "bm1_tp10_stop15": V(bear_min=0.01, tp=0.10, stop=0.15, fill="next"),
       "bm1_tp10_stop8": V(bear_min=0.01, tp=0.10, stop=0.08, fill="next")}
F = json.load(open(B + r"\plan\pa_out\lm1_fixed.json"))
def net(r, b): return 1e4 * r - b * (2 + r)
res = {}
for s in ("R4", "RND", "HF3"):
    rows = F["sets"][s]; ent = []
    if s == "HF3":
        for x in json.load(open(B + r"\data\massive\rotation_trades_C37F_hf3.json")):
            ent.append((x["date"], x["symbol"], L.mgrid(int(x["entry_time"][11:13]), int(x["entry_time"][14:16])), x["entry"]))
    else:
        d = json.load(open(B + r"\plan\pa_out\cp_r4_legs.json"))["legs"]
        for k in (["R4"] if s == "R4" else [f"RND{i}" for i in range(5)]):
            ent += [(x["date"], x["sym"], x["entry_min"], x["entry"]) for x in d[k]]
    byd = collections.defaultdict(list)
    for j, e in enumerate(ent): byd[e[0]].append(j)
    out = {v: [None] * len(ent) for v in VAR}
    for date, J in byd.items():
        day = L.load_day(date); idx = {sy: i for i, sy in enumerate(day.syms)}
        for j in J:
            i = idx.get(ent[j][1])
            if i is None: continue
            for vn, x in VAR.items():
                m, px, why = walk(day, i, ent[j][2], ent[j][3], x)
                if m is not None: out[vn][j] = px / ent[j][3] - 1
    print(f"\n## {s} n={len(ent)} dates {min(e[0] for e in ent)}..{max(e[0] for e in ent)}")
    print("| stack | gross $/tkt | net@15 | net@28.75 | Y1 net@15 | Y2 net@15 | worst leg $ | ex-top5 gross | months+ @15 |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for vn in VAR:
        J = [j for j in range(len(ent)) if out[vn][j] is not None]
        r = np.array([out[vn][j] for j in J]); y1 = np.array([ent[j][0] < "2025-08-01" for j in J])
        mon = collections.defaultdict(float)
        for j, x in zip(J, net(r, 15)): mon[ent[j][0][:7]] += x
        p = 1e4 * r
        print(f"| {vn} | {p.mean():+.1f} | {net(r,15).mean():+.1f} | {net(r,28.75).mean():+.1f} | {net(r[y1],15).mean():+.1f} | {net(r[~y1],15).mean():+.1f} | {p.min():+,.0f} | {(p.sum()-np.sort(p)[-5:].sum())/len(p):+.1f} | {sum(v>0 for v in mon.values())}/{len(mon)} |")
