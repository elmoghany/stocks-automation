"""LEGACY-13 step 6: analyse the random-pick legs by range forecast."""
import json, math
import numpy as np
X = json.load(open(__file__.replace("lm13_rnd_an.py", "lm13_rnd_legs.json")))
A = lambda k: np.array([x[k] for x in X], float)
r = A("ret") * 1e4; s = A("sigma1"); sc = A("score"); dv = A("dvol_now")
mfe = np.array([x["mfe_mae"][0] for x in X]); mae = np.array([x["mfe_mae"][1] for x in X])
h1 = np.array([x["date"] < "2025-09-12" for x in X])
day = np.array([x["date"] for x in X]); seed = A("seed")
def row(lab, m):
    v = r[m]; srt = np.sort(v)
    # cluster SE by date (legs on one date share the tape)
    dm = {}
    for d, x in zip(day[m], v): dm.setdefault(d, []).append(x)
    per = np.array([np.mean(z) for z in dm.values()])
    se = per.std(ddof=1) / math.sqrt(len(per))
    print(f"{lab:26s} n={m.sum():5d} mean {v.mean():+7.1f} (se~{se:4.1f}) trim1% "
          f"{srt[int(.01*len(v)):int(.99*len(v))].mean():+7.1f} med {np.median(v):+6.1f} "
          f"win {100*(v>0).mean():4.1f}% H1 {r[m&h1].mean():+7.1f} H2 {r[m&~h1].mean():+7.1f} "
          f"rng_med {np.nanmedian(mfe[m]-mae[m]):.3f} dvol_med {np.nanmedian(dv[m])/1e3:7.0f}k")
print("random-pick legs, R4 exits, gross $ per $10k ticket")
row("all", np.ones(len(r), bool))
row("sigma nan (thin)", ~np.isfinite(s))
f = np.isfinite(s)
for lo, hi in [(0, .0086), (.0086, .0170), (.0170, 9)]:
    row(f"sigma {lo:.4f}-{hi:.4f}", f & (s > lo) & (s <= hi))
q = np.nanpercentile(s[h1 & f], [20, 40, 60, 80])
print("H1 quintile cuts", np.round(q, 4))
e = [0, *q, 9]
for j in range(5):
    row(f"sigma Q{j+1}", f & (s > e[j]) & (s <= e[j+1]))
g = np.isfinite(sc)
qs = np.nanpercentile(sc[h1 & g], [33.3, 66.7]) if (h1 & g).any() else np.nanpercentile(sc[g], [33.3, 66.7])
print("score cuts", qs, "scored legs", g.sum())
for j, (lo, hi) in enumerate([(-1, qs[0]), (qs[0], qs[1]), (qs[1], 2)]):
    row(f"up30 score T{j+1}", g & (sc > lo) & (sc <= hi))
# within the high-sigma bucket, does the model score add anything?
hi_ = f & (s > .0170) & g
if hi_.sum() > 50:
    c = np.median(sc[hi_])
    row("hi sigma & score<med", hi_ & (sc <= c)); row("hi sigma & score>med", hi_ & (sc > c))
