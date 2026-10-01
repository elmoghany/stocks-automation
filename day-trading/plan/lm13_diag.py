"""LEGACY-13 step 2: does the causal range forecast at entry predict the
R4 leg's forward range, its return, and its exit outcome?"""
import json

import numpy as np

D = json.load(open(__file__.replace("lm13_diag.py", "lm13_base_legs.json")))
legs = D["legs"]


def arr(k):
    return np.array([x[k] for x in legs], float)


def spear(a, b):
    ok = np.isfinite(a) & np.isfinite(b)
    ra = np.argsort(np.argsort(a[ok]))
    rb = np.argsort(np.argsort(b[ok]))
    return float(np.corrcoef(ra, rb)[0, 1]), int(ok.sum())


notl = arr("shares") * arr("entry")
ret = arr("gross") / notl
mfe, mae = arr("mfe"), arr("mae")
rng = mfe - mae
hold = arr("exit_min") - arr("entry_min")
g10 = ret * 10_000                      # $ per $10k, gross
print("n", len(legs), "scored", int(np.isfinite(arr("score")).sum()))
print("proxy           rho(range)  rho(mfe)  rho(-mae)  rho(ret)   n")
for k in ("score", "sigma1", "hi_gain", "rvol_now", "prior_range",
          "prevrange", "gain_now", "dvol_now", "last"):
    a = arr(k)
    print(f"{k:14s} {spear(a, rng)[0]:+.3f}     {spear(a, mfe)[0]:+.3f}"
          f"    {spear(a, -mae)[0]:+.3f}    {spear(a, ret)[0]:+.3f}"
          f"  {spear(a, rng)[1]}")

reasons = np.array([x["reason"].split()[0] for x in legs])
for k in ("sigma1", "score"):
    a = arr(k)
    ok = np.isfinite(a)
    q = np.nanpercentile(a[ok], [33.33, 66.67])
    print(f"\n== terciles of {k} (cuts {q[0]:.4g}, {q[1]:.4g}) ==")
    print("terc  n   gross$/10k  med   win%  mfe_med mae_med range_med "
          "hold_med trail% bear% flat%  top5share")
    for j, (lo, hi) in enumerate([(-np.inf, q[0]), (q[0], q[1]),
                                  (q[1], np.inf)]):
        m = ok & (a > lo) & (a <= hi)
        gg = g10[m]
        srt = np.sort(gg)
        t5 = srt[-5:].sum() / gg.sum() if gg.sum() else np.nan
        print(f"T{j+1}  {m.sum():4d}  {gg.mean():+8.1f}  {np.median(gg):+6.1f}"
              f"  {100*(gg>0).mean():4.1f}  {np.median(mfe[m]):.3f}  "
              f"{np.median(mae[m]):+.3f}  {np.median(rng[m]):.3f}   "
              f"{np.median(hold[m]):5.0f}  "
              f"{100*(reasons[m]=='trail').mean():4.0f}  "
              f"{100*(reasons[m]=='bearish').mean():4.0f}  "
              f"{100*(reasons[m]=='flatten').mean():4.0f}  {t5:+.2f}")
    # exit efficiency: realised ret as share of mfe
    for j, (lo, hi) in enumerate([(-np.inf, q[0]), (q[0], q[1]),
                                  (q[1], np.inf)]):
        m = ok & (a > lo) & (a <= hi)
        print(f"  T{j+1} mean ret {ret[m].mean():+.4f} mean mfe "
              f"{mfe[m].mean():.4f} mean mae {mae[m].mean():+.4f} "
              f"p90 mfe {np.percentile(mfe[m], 90):.3f}  "
              f"sd ret {ret[m].std():.4f}")
