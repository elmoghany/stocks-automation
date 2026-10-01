"""LEGACY-11: NaN-safe re-cut of A2 (P10 IC) and A3 (continuation) from lm11_A.npy."""
import sys
from pathlib import Path
import numpy as np
from scipy.stats import rankdata
A = np.load(Path(sys.argv[1]) / "lm11_A.npy")
NDAY = int(A[:, 0].max()) + 1
HALF = NDAY // 2
W = lambda x: np.clip(x, -0.5, 0.5)
print("finite P10", np.isfinite(A[:, 2]).mean(), "finite ret30", np.isfinite(A[:, 4]).mean())
grp = A[:, 0] * 1000 + A[:, 1]
o = np.argsort(grp, kind="stable"); A = A[o]; grp = grp[o]
cuts = np.flatnonzero(np.diff(grp)) + 1
st = np.concatenate([[0], cuts]); en = np.concatenate([cuts, [len(A)]])
res = {}
for s0, e0 in zip(st, en):
    g = A[s0:e0]
    ok = np.isfinite(g[:, 2]) & np.isfinite(g[:, 4])
    g = g[ok]
    if len(g) < 5:
        continue
    rp = rankdata(g[:, 2]); rr = rankdata(g[:, 4])
    x = rr - rr.mean(); y = rp - rp.mean()
    rres = rankdata(y - (x @ y) / (x @ x) * x) if x @ x > 0 else rp
    for j, h in enumerate((1, 5, 15, 30)):
        ry = rankdata(g[:, 8 + j])
        for fn, rx in (("P10", rp), ("P10|ret30", rres)):
            if rx.std() > 0 and ry.std() > 0:
                res.setdefault((fn, h), []).append((g[0, 0], np.corrcoef(rx, ry)[0, 1]))
for k, v in res.items():
    v = np.array(v); d = v[:, 0].astype(int)
    dm = np.bincount(d, v[:, 1], NDAY)[np.bincount(d, minlength=NDAY) > 0] / np.bincount(d)[np.bincount(d, minlength=NDAY) > 0]
    print(f"{k[0]:10s} f{k[1]:<3d} IC {v[:,1].mean():+.4f} t {dm.mean()/(dm.std(ddof=1)/np.sqrt(len(dm))):+.2f} Y1 {v[d<HALF,1].mean():+.4f} Y2 {v[d>=HALF,1].mean():+.4f} n {len(v)}")
B = A[np.isfinite(A[:, 4])]
q1, q2 = np.quantile(B[:, 4], [1/3, 2/3])
print(f"\nA3 ret30 tercile cuts {q1:+.4f} {q2:+.4f}; fwd30 / fwd5 bps by P30 bucket")
for lab, s in (("down", B[:, 4] < q1), ("mid", (B[:, 4] >= q1) & (B[:, 4] < q2)), ("up", B[:, 4] >= q2)):
    out = []
    for lo, hi in ((-1.01, -0.3), (-0.3, 0.3), (0.3, 1.01)):
        z = s & (B[:, 3] >= lo) & (B[:, 3] < hi)
        out.append(f"{1e4*W(B[z,11]).mean():+6.1f}/{1e4*W(B[z,9]).mean():+5.1f} n={z.sum()}")
    hi_ = s & (B[:, 3] >= 0.3); lo_ = s & (B[:, 3] < -0.3)
    di = lambda z: (np.bincount(B[z, 0].astype(int), W(B[z, 11]), NDAY), np.bincount(B[z, 0].astype(int), minlength=NDAY))
    (sh, nh), (sl, nl) = di(hi_), di(lo_)
    both = (nh > 0) & (nl > 0)
    d = sh[both] / nh[both] - sl[both] / nl[both]
    print(f"{lab:5s} P<=-.3 {out[0]} | mid {out[1]} | P>=.3 {out[2]} | hi-lo f30 {1e4*d.mean():+.1f} t={d.mean()/(d.std(ddof=1)/np.sqrt(len(d))):+.2f}")
