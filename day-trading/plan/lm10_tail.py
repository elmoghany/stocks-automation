"""LEGACY-10 part 2: is the gapper POOL's quality (30 random-pick controls) or
R4's right-tail frequency predictable from pre-day regime features?
argv[1] = lm10_feat.pkl (panel pickle sits beside it)."""
import json, os, sys, pickle
import numpy as np

HERE = os.path.dirname(__file__)
P = pickle.load(open(sys.argv[1].replace("feat", "panel"), "rb"))
D = json.load(open(os.path.join(HERE, "pa_out", "cp_r4_legs.json")))
feat, dates = P["feat"], P["dates"]
N = len(dates); di = {d: i for i, d in enumerate(dates)}
y1 = np.array([d < "2025-08-01" for d in dates]); y2 = ~y1
BPS = 15


def per_day(legs, thr=0.15, clip=0.15):
    s = np.zeros(N); n = np.zeros(N); tail = np.zeros(N); sc = np.zeros(N)
    for t in legs:
        r = t["exit"] / t["entry"] - 1; i = di[t["date"]]
        s[i] += r; sc[i] += max(-clip, min(clip, r)); n[i] += 1; tail[i] += r >= thr
    return s, sc, n, tail

r4 = per_day(D["legs"]["R4"])
rn = [per_day(D["legs"][f"RND{k}"]) for k in range(30)]
rn_sc = np.sum([x[1] for x in rn], 0); rn_n = np.sum([x[2] for x in rn], 0); rn_tail = np.sum([x[3] for x in rn], 0)
pool_q = np.where(rn_n > 0, rn_sc / np.maximum(rn_n, 1), np.nan)     # clipped mean return per random ticket
pool_tail = np.where(rn_n > 0, rn_tail / np.maximum(rn_n, 1), np.nan)

def spear(a, b):
    m = np.isfinite(a) & np.isfinite(b)
    ra = np.argsort(np.argsort(a[m])); rb = np.argsort(np.argsort(b[m]))
    return np.corrcoef(ra, rb)[0, 1], m.sum()

print("pool tail rate (P random leg >= +15%):", f"Y1 {np.nansum(rn_tail[y1])/rn_n[y1].sum():.4f}  Y2 {np.nansum(rn_tail[y2])/rn_n[y2].sum():.4f}")
print("R4 tail rate:", f"Y1 {r4[3][y1].sum()/r4[2][y1].sum():.4f} ({r4[3][y1].sum():.0f})  Y2 {r4[3][y2].sum()/r4[2][y2].sum():.4f} ({r4[3][y2].sum():.0f})")
print("pool clipped mean ret/ticket: Y1 %+.4f Y2 %+.4f" % (rn_sc[y1].sum() / rn_n[y1].sum(), rn_sc[y2].sum() / rn_n[y2].sum()))
print("\n== daily Spearman IC of pre-day feature vs (a) pool quality, (b) pool tail rate, (c) R4 clipped day mean ==")
print("   |IC| > ~0.14 (Y1, n~190) / ~0.125 (Y2, n~250) is 2-sigma; 75 features => expect ~4 false hits per column")
r4_q = np.where(r4[2] > 0, r4[1] / np.maximum(r4[2], 1), np.nan)
rows = []
for k, f in feat.items():
    a1, n1 = spear(f[y1], pool_q[y1]); a2, n2 = spear(f[y2], pool_q[y2])
    b1, _ = spear(f[y1], pool_tail[y1]); b2, _ = spear(f[y2], pool_tail[y2])
    c1, _ = spear(f[y1], r4_q[y1]); c2, _ = spear(f[y2], r4_q[y2])
    rows.append((k, a1, a2, b1, b2, c1, c2, n1))
rows.sort(key=lambda r: -abs(r[1] + r[2]))
both = 0
for k, a1, a2, b1, b2, c1, c2, n1 in rows:
    same = np.sign(a1) == np.sign(a2) and min(abs(a1), abs(a2)) > 0.10
    both += same
    print(f"  {k:13s} pool Y1 {a1:+.3f} Y2 {a2:+.3f} {'*' if same else ' '} | tail Y1 {b1:+.3f} Y2 {b2:+.3f} | R4 Y1 {c1:+.3f} Y2 {c2:+.3f}  n1={n1}")
print("features with |pool IC|>0.10 and same sign both years:", both)

# raw-P&L walk-forward judged per traded ticket vs random sit-out of the same size
g_raw = P["g_raw"]; n = P["n"]
rng = np.random.default_rng(7)
print("\n== frozen Y1-fit rules on raw Y2 P&L at 15 bps: per-ticket on-days vs random day-subsets of same size ==")
base_pt = g_raw[y2].sum() / n[y2].sum()
res = []
for k, f in feat.items():
    ok = np.isfinite(f)
    if ok[y1].sum() < 100:
        continue
    for qq in (1 / 3, 1 / 2, 2 / 3):
        cut = np.nanquantile(f[y1 & ok], qq)
        for side in ("ge", "le"):
            on = ((f >= cut) if side == "ge" else (f <= cut)) | ~ok
            fit_pt = g_raw[y1 & on].sum() / max(n[y1 & on].sum(), 1)
            res.append((fit_pt, k, qq, side, on))
res.sort(key=lambda r: -r[0])
idx2 = np.where(y2)[0]
for fit_pt, k, qq, side, on in res[:10]:
    m = y2 & on
    pt = g_raw[m].sum() / max(n[m].sum(), 1)
    nd = m.sum()
    null = []
    for _ in range(500):
        s = rng.choice(idx2, nd, replace=False)
        null.append(g_raw[s].sum() / max(n[s].sum(), 1))
    print(f"  {k:13s} {side} q{qq:.2f}: Y1 on-day $/tk {fit_pt:+.0f} | Y2 on-day $/tk {pt:+.0f} vs Y2 all {base_pt:+.0f}; "
          f"random-subset pct {100*(np.array(null)<pt).mean():.0f}  days {nd}/{y2.sum()}")
