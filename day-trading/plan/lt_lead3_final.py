"""LEADS-TEST lead 3: book-level variants of the guarded rule (first event per
day / up to 10 per day by cross time), months positive, halal-PASS line.
    python plan/lt_lead3_final.py"""
import sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
import lt_lead3_ctl as K
import lt_lead3_report as R
import lt_lib as LL
import cp_lib as L

rows = sorted([e for e in K.EV if K.sel(e)], key=lambda e: (e["date"], e["em"]))
nd = {sp: sum(1 for d in L.panel_dates() if LL.split_of(d) == sp) for sp in ("Y1", "Y2", "OOS")}
nd["ALL"] = sum(nd.values())
byd = {}
for e in rows:
    byd.setdefault(e["date"], []).append(e)
first = [v[0] for v in byd.values()]
cap10 = [x for v in byd.values() for x in v[:10]]
print("days with >=1 event", len(byd), "max events/day", max(len(v) for v in byd.values()))
R.hdr()
R.line("guarded, all events (<=10/day)", cap10, nd)
R.line("guarded, FIRST event of the day only", first, nd)
R.line("guarded, halal-PASS (present list)", [e for e in rows if e["sym"] in L.halal_set()], nd)
lg = R.legs(rows)
mon = {}
for x in lg:
    mon[x["date"][:7]] = mon.get(x["date"][:7], 0) + x["n_c"]
print("months positive (central):", sum(v > 0 for v in mon.values()), "/", len(mon))
print(" ".join(f"{k}:{v:+.0f}" for k, v in sorted(mon.items())))
# entry time buckets
for lo, hi in ((180, 240), (240, 300), (300, 330)):
    v = [1e4 * e["x1000"] for e in rows if lo <= e["t"] < hi]
    print(f"cross {4+lo//60:02d}:{lo%60:02d}-{4+hi//60:02d}:{hi%60:02d}: n {len(v)} gross {np.mean(v):+.1f}")
