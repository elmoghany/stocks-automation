"""LEGACY-11: summarise lm11_B2.pkl (exit variants), overall and by liquidity."""
import sys, pickle
from pathlib import Path
import numpy as np
T = pickle.load(open(Path(sys.argv[1]) / sys.argv[2] if len(sys.argv) > 2 else "lm11_B2.pkl", "rb"))
keys, M, R, ND = T["keys"], T["M"], T["R"], T["ndays"]
HALF = ND // 2
days = M[:, 0].astype(int)
def dt(d, dd):
    s = np.bincount(dd, d, ND); n = np.bincount(dd, minlength=ND); m = s[n > 0] / n[n > 0]
    return m.mean() / (m.std(ddof=1) / np.sqrt(len(m)))
for lab, sel in (("ALL", np.ones(len(M), bool)),
                 ("dv30 >= $1M (liquid)", M[:, 2] >= 1e6),
                 ("dv30 < $1M", M[:, 2] < 1e6),
                 ("entry <= 10:30", M[:, 1] <= 390)):
    Rs, ds = R[sel], days[sel]
    H = Rs[:, keys.index("H")]
    print(f"\n== {lab}: n={sel.sum()} ({sel.sum()/ND:.1f}/day)  H gross {1e4*H.mean():+.1f} bps = ${1e4*H.mean():+.2f}/trade @ $10k")
    print("rule   gross$/tr  d_vs_H$  t(day)   Y1d$   Y2d$  ex-top10d$  months+ (d>0)")
    for k in keys:
        r = Rs[:, keys.index(k)]; d = r - H
        srt = np.argsort(d)
        ex = np.delete(d, srt[-10:]).mean() * 1e4
        mo = ds // 21
        mpos = sum(1 for q in np.unique(mo) if d[mo == q].mean() > 0)
        print(f"{k:6s} {1e4*r.mean():+8.2f} {1e4*d.mean():+8.2f} {dt(d, ds):+6.2f} {1e4*d[ds<HALF].mean():+6.2f} {1e4*d[ds>=HALF].mean():+6.2f} {ex:+9.2f}   {mpos}/{len(np.unique(mo))}")
