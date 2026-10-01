"""LEGACY-1 mode B: fixed entries (R4, RND0-4, C37F-hf3), every exit variant.
Output: plan/pa_out/lm1_fixed.json (per variant per set: arrays of r and dates)."""
import json, sys, time, collections
import numpy as np
sys.path.insert(0, r"C:\cornell\stocks-automation\day-trading\plan")
import cp_lib as L
from lm1_walk import V, walk
B = r"C:\cornell\stocks-automation\day-trading"
VAR = {
 "base_close": V(), "base_next": V(fill="next"),
 "stop8": V(stop=0.08), "notrail": V(trail=False), "notrail_next": V(trail=False, fill="next"),
 "nobear": V(bear=False), "hold1500": V(trail=False, bear=False),
 "hold1200": V(trail=False, bear=False, end=L.mgrid(12)),
 "base_end1200": V(end=L.mgrid(12)), "base_end1300": V(end=L.mgrid(13)),
 "t30": V(tstop=30, fill="next"), "t60": V(tstop=60, fill="next"),
 "t90": V(tstop=90, fill="next"), "t120": V(tstop=120, fill="next"),
 "red30": V(tstop_red=(30, 0.0), fill="next"), "red60": V(tstop_red=(60, 0.0), fill="next"),
 "red90": V(tstop_red=(90, 0.0), fill="next"),
 "vwap": V(vwap=True, vwap_min=5, fill="next"), "vwap_only": V(trail=False, bear=False, vwap=True, vwap_min=5, fill="next"),
 "atr3": V(atr_k=3, fill="next"), "atr3_only": V(trail=False, bear=False, atr_k=3, fill="next"),
 "atr5_only": V(trail=False, bear=False, atr_k=5, fill="next"),
 "tp2": V(tp=0.02, bear=False), "tp3": V(tp=0.03, bear=False), "tp5": V(tp=0.05, bear=False),
 "tp10": V(tp=0.10, bear=False), "tp5_bear": V(tp=0.05, fill="next"),
 "lock3": V(lock_at=0.03, lock_to=0.005, fill="next"),
 "bear_min1": V(bear_min=0.01, fill="next"), "bear_any": V(bear_any=True, fill="next"),
 "stop5": V(stop=0.05, fill="next"), "stop3": V(stop=0.03, fill="next"),
}
sets = collections.defaultdict(list)   # set -> [(date, sym, em, entry, base_reason)]
d = json.load(open(B + r"\plan\pa_out\cp_r4_legs.json"))
for x in d["legs"]["R4"]:
    sets["R4"].append((x["date"], x["sym"], x["entry_min"], x["entry"], x["reason"], x["exit"]))
for k in range(5):
    for x in d["legs"][f"RND{k}"]:
        sets["RND"].append((x["date"], x["sym"], x["entry_min"], x["entry"], x["reason"], x["exit"]))
for x in json.load(open(B + r"\data\massive\rotation_trades_C37F_hf3.json")):
    hh, mm = int(x["entry_time"][11:13]), int(x["entry_time"][14:16])
    sets["HF3"].append((x["date"], x["symbol"], L.mgrid(hh, mm), x["entry"], x["reason"], x["exit"]))
bydate = collections.defaultdict(list)
for s, rows in sets.items():
    for j, r in enumerate(rows):
        bydate[r[0]].append((s, j, r))
out = {s: {v: [None] * len(rows) for v in VAR} for s, rows in sets.items()}
mfe = {s: [None] * len(rows) for s, rows in sets.items()}
miss = collections.Counter(); t0 = time.time()
for n, date in enumerate(sorted(bydate)):
    day = L.load_day(date)
    if day is None:
        miss["noday"] += len(bydate[date]); continue
    idx = {s: i for i, s in enumerate(day.syms)}
    for s, j, (dt, sym, em, entry, _, _) in bydate[date]:
        i = idx.get(sym)
        if i is None:
            miss[s] += 1; continue
        for vn, x in VAR.items():
            m, px, why = walk(day, i, em, entry, x)
            if m is not None:
                out[s][vn][j] = (px / entry - 1, why, m - em)
        # MFE/MAE to the base(next) exit and to 15:00, path stats
        m_b = out[s]["base_next"][j]
        if m_b is not None:
            seg = slice(em, em + m_b[2] + 1)
            hh = np.nanmax(day.h[i, seg]); ll = np.nanmin(day.l[i, seg])
            seg2 = slice(em, L.M_1500 + 1)
            mfe[s][j] = (hh / entry - 1, ll / entry - 1, np.nanmax(day.h[i, seg2]) / entry - 1, np.nanmin(day.l[i, seg2]) / entry - 1)
    if (n + 1) % 50 == 0:
        print(n + 1, len(bydate), round(time.time() - t0), flush=True)
json.dump({"sets": {s: [r[:2] + (r[4],) for r in rows] for s, rows in sets.items()},
           "out": out, "mfe": mfe, "miss": dict(miss)},
          open(B + r"\plan\pa_out\lm1_fixed.json", "w"), default=float)
print("done", round(time.time() - t0), dict(miss))
