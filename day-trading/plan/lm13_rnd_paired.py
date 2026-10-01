"""LEGACY-13 step 7: paired exit test on RANDOM-pick legs (seeds 0-3),
entries fixed, exits varied by the range forecast at the decision minute.
Removes R4's own pick-luck from the exit question."""
import json, math
from collections import defaultdict
import numpy as np
import lm13_policy as P
M, S, F, L = P.M, P.S, P.F, P.L
LO, HI, MED = P.LO_CUT, P.HI_CUT, P.MED
X = [x for x in json.load(open(M.PLAN / "lm13_rnd_legs.json")) if x["seed"] < 4]
BASE = S.default_cfg(rank="none", stop_pct=None)
def cfg_for(n, s):
    fin = np.isfinite(s); c = dict(BASE)
    if n.startswith("trail_m") and fin:
        tw = float(np.clip(float(n[7:]) * s, .03, .40)); c.update(trail_pct=tw, trail_lo=tw/2, trail_hi=min(2*tw, .6))
    elif n == "trail30_hi" and fin and s > HI: c.update(trail_pct=.30, trail_lo=.15, trail_hi=.50)
    elif n == "trail30_all": c.update(trail_pct=.30, trail_lo=.15, trail_hi=.50)
    elif n == "trail10_all": c.update(trail_pct=.10, trail_lo=.05, trail_hi=.20)
    elif n.startswith("tgtsig"): c["tgt_full"] = float(n[6:]) * (s if fin else MED)
    elif n.startswith("tgtflat"): c["tgt_full"] = float(n[7:]) * MED
    elif n == "nobear_hi" and fin and s > HI: c["bearish_exit"] = False
    elif n == "nobear_all": c["bearish_exit"] = False
    return c
NAMES = ["base", "trail_m8", "trail_m12", "trail_m20", "trail30_hi", "trail30_all", "trail10_all",
         "tgtsig3", "tgtsig6", "tgtsig12", "tgtflat3", "tgtflat6", "nobear_hi", "nobear_all"]
byd = defaultdict(list)
for k, x in enumerate(X): byd[x["date"]].append(k)
R = {n: np.full(len(X), np.nan) for n in NAMES}
for d, ks in byd.items():
    Fd = F.load(d); day = L.load_day(d); si = {s: i for i, s in enumerate(day.syms)}
    for k in ks:
        x = X[k]; i = si[x["sym"]]; em = x["entry_min"]; px = float(day.o[i, em])
        for n in NAMES:
            m, ex, _ = S._walk_exit(day, Fd, i, em, px, cfg_for(n, x["sigma1"]))
            if ex is not None: R[n][k] = ex / px - 1
s = np.array([x["sigma1"] for x in X]); h1 = np.array([x["date"] < "2025-09-12" for x in X])
dd = np.array([x["date"] for x in X])
print("base reproduces:", np.nanmax(np.abs(R["base"] - np.array([x["ret"] for x in X]))), "n", len(X))
G = {"all": np.isfinite(R["base"]), "lo": s <= LO, "mid": (s > LO) & (s <= HI), "hi": s > HI, "H1": h1, "H2": ~h1}
res = {}
print("gross $/10k (paired delta vs base, date-clustered t)")
for n in NAMES:
    cells = []; res[n] = {}
    for g, m in G.items():
        m = m & np.isfinite(R[n]) & np.isfinite(R["base"])
        dl = (R[n][m] - R["base"][m]) * 1e4
        per = defaultdict(list)
        for d_, v in zip(dd[m], dl): per[d_].append(v)
        pv = np.array([np.mean(v) for v in per.values()])
        t = pv.mean() / (pv.std(ddof=1) / math.sqrt(len(pv)) + 1e-12)
        res[n][g] = dict(n=int(m.sum()), mean=float(R[n][m].mean() * 1e4), d=float(dl.mean()), t=float(t))
        cells.append(f"{R[n][m].mean()*1e4:+6.0f}({dl.mean():+5.0f},{t:+4.1f})")
    print(f"{n:12s} " + " ".join(f"{c:>17s}" for c in cells))
json.dump(res, open(M.PLAN / "lm13_rnd_paired.json", "w"))
