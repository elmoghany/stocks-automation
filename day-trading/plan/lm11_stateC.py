"""LEGACY-11: held-state cut -- remaining return (next open -> 14:59) by P10 decile,
for positions >5% above their +10%-cross entry; year split; day-clustered."""
import sys
from pathlib import Path
import numpy as np
S = np.load(Path(sys.argv[1]) / "lm11_S.npy")
ND = int(S[:, 0].max()) + 1; HALF = ND // 2
W = lambda x: np.clip(x, -0.5, 0.5)
for lab, s in (("gain>5%", S[:, 3] > 0.05), ("gain>15%", S[:, 3] > 0.15), ("all", np.ones(len(S), bool))):
    z = s & np.isfinite(S[:, 1])
    qs = np.quantile(S[z, 1], np.linspace(0, 1, 11))
    b = np.clip(np.digitize(S[:, 1], qs[1:-1]), 0, 9)
    print(f"\n{lab}: P10 decile -> mean to-flat bps (Y1/Y2), n")
    for k in range(10):
        q = z & (b == k)
        y1 = q & (S[:, 0] < HALF); y2 = q & (S[:, 0] >= HALF)
        print(f"  d{k} P10 [{qs[k]:+.2f},{qs[k+1]:+.2f}) {1e4*W(S[q,6]).mean():+7.1f} ({1e4*W(S[y1,6]).mean():+6.1f}/{1e4*W(S[y2,6]).mean():+6.1f}) n={q.sum()} days={len(np.unique(S[q,0]))}")
