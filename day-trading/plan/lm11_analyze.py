"""LEGACY-11 analysis of the arrays written by lm11_pressure.py.

    python plan/lm11_analyze.py <outdir>
"""
import pickle
import sys
from pathlib import Path

import numpy as np
from scipy.stats import rankdata

OUT = Path(sys.argv[1])
A = np.load(OUT / "lm11_A.npy")
S = np.load(OUT / "lm11_S.npy")
T = pickle.load(open(OUT / "lm11_T.pkl", "rb"))
NDAY = int(A[:, 0].max()) + 1
HALF = NDAY // 2
HOR = (1, 5, 15, 30)
# A: 0 di,1 m,2 P10,3 P30,4 ret30,5 ret5,6 prng,7 bounce,8..11 fwd,12..15 range
W = lambda x: np.clip(x, -0.5, 0.5)


def day_t(vals, days):
    """mean and t-stat with the DAY as the unit (clustered)."""
    ok = np.isfinite(vals)
    vals, days = vals[ok], days[ok].astype(int)
    s = np.bincount(days, vals, minlength=NDAY)
    n = np.bincount(days, minlength=NDAY)
    dm = s[n > 0] / n[n > 0]
    return vals.mean(), dm.mean() / (dm.std(ddof=1) / np.sqrt(len(dm)))


print("rows", len(A), "days", NDAY, "trades", len(T["TR"]), "states", len(S))
print("\n== A1. pooled buckets of P30 (fwd from next-bar OPEN, winsorised +-50%, bps) ==")
bins = [-1.01, -0.3, -0.1, 0.1, 0.3, 1.01]
for col, name in ((3, "P30"), (2, "P10")):
    print(f"-- {name}")
    print("bucket          n       f1     f5    f15    f30   rng30  pastrng30  ret30")
    b = np.digitize(A[:, col], bins) - 1
    for k in range(5):
        s = b == k
        print(f"[{bins[k]:+.1f},{bins[k+1]:+.1f}) {s.sum():7d} " +
              " ".join(f"{1e4*W(A[s, 8+j]).mean():6.1f}" for j in range(4)) +
              f" {1e4*A[s, 15].mean():6.0f} {1e4*A[s, 6].mean():9.0f} {1e4*A[s, 4].mean():6.0f}")

print("\n== A2. cross-sectional rank IC per (day, minute) group >= 5 names; day-clustered t ==")
grp = A[:, 0] * 1000 + A[:, 1]
order = np.argsort(grp, kind="stable")
A = A[order]
grp = grp[order]
cuts = np.flatnonzero(np.diff(grp)) + 1
starts = np.concatenate([[0], cuts])
ends = np.concatenate([cuts, [len(A)]])


def resid(y, x):
    x = x - x.mean()
    y = y - y.mean()
    d = (x * x).sum()
    return y - (x * y).sum() / d * x if d > 0 else y


feats = {"P10": 2, "P30": 3, "ret30": 4, "ret5": 5}
targets = {f"f{h}": 8 + j for j, h in enumerate(HOR)}
targets.update({"rng30/past": None})
res = {}
for s0, e0 in zip(starts, ends):
    if e0 - s0 < 5:
        continue
    g = A[s0:e0]
    di = g[0, 0]
    rk = {k: rankdata(g[:, c]) for k, c in feats.items()}
    rk["P30|ret30"] = rankdata(resid(rk["P30"], rk["ret30"]))
    rk["|P30|"] = rankdata(np.abs(g[:, 3]))
    for tn, tc in targets.items():
        y = g[:, tc] if tc is not None else g[:, 15] / np.maximum(g[:, 6], 1e-4)
        if not np.isfinite(y).all():
            continue
        ry = rankdata(y)
        for fn, rx in rk.items():
            if np.std(rx) == 0:
                continue
            res.setdefault((fn, tn), []).append((di, np.corrcoef(rx, ry)[0, 1]))
print("feature     target       meanIC    t(day)   Y1IC    Y2IC  n_groups")
for (fn, tn), v in res.items():
    v = np.array(v)
    v = v[np.isfinite(v[:, 1])]
    m, t = day_t(v[:, 1], v[:, 0])
    y1 = v[v[:, 0] < HALF, 1].mean()
    y2 = v[v[:, 0] >= HALF, 1].mean()
    print(f"{fn:10s} {tn:12s} {m:+.4f}  {t:+6.2f}  {y1:+.4f} {y2:+.4f} {len(v)}")

print("\n== A3. continuation: ret30 tercile x P30 (fwd30 bps, winsorised) ==")
q1, q2 = np.quantile(A[:, 4], [1 / 3, 2 / 3])
print(f"ret30 tercile cuts {q1:+.3f} {q2:+.3f}")
for lab, s in (("down", A[:, 4] < q1), ("mid", (A[:, 4] >= q1) & (A[:, 4] < q2)), ("up", A[:, 4] >= q2)):
    row = []
    for lo, hi in ((-1.01, -0.3), (-0.3, 0.3), (0.3, 1.01)):
        z = s & (A[:, 3] >= lo) & (A[:, 3] < hi)
        row.append(f"{1e4*W(A[z, 11]).mean():+6.1f} (n={z.sum()})")
    hi_ = s & (A[:, 3] >= 0.3)
    lo_ = s & (A[:, 3] < -0.3)
    # day-clustered hi-minus-lo
    dh = np.bincount(A[hi_, 0].astype(int), W(A[hi_, 11]), NDAY) / np.maximum(np.bincount(A[hi_, 0].astype(int), minlength=NDAY), 1)
    dl = np.bincount(A[lo_, 0].astype(int), W(A[lo_, 11]), NDAY) / np.maximum(np.bincount(A[lo_, 0].astype(int), minlength=NDAY), 1)
    both = (np.bincount(A[hi_, 0].astype(int), minlength=NDAY) > 0) & (np.bincount(A[lo_, 0].astype(int), minlength=NDAY) > 0)
    d = (dh - dl)[both]
    print(f"{lab:5s} P<=-.3 {row[0]} | mid {row[1]} | P>=.3 {row[2]} | hi-lo {1e4*d.mean():+.1f} bps t={d.mean()/(d.std(ddof=1)/np.sqrt(len(d))):+.2f}")

print("\n== A4. bounce check: close(m) vs open(m+1) by P10 bucket (bps) ==")
b = np.digitize(A[:, 2], bins) - 1
print(" ".join(f"{1e4*A[b == k, 7].mean():+.1f}" for k in range(5)))

print("\n== B. exit rules on every first RTH +10% close-cross (enter next open, flatten 14:59) ==")
keys, TR, meta = T["keys"], T["TR"], T["meta"]
days = meta[:, 0]
H = TR[:, keys.index("H")]
print("rule        mean_bps  $/trade@10k  d_vs_H$   t(day)   Y1 d$   Y2 d$  ex-top10 d$  hit%exit")
for k in keys:
    r = TR[:, keys.index(k)]
    d = r - H
    m, t = day_t(d, days)
    y1 = d[days < HALF].mean() * 1e4
    y2 = d[days >= HALF].mean() * 1e4
    srt = np.argsort(d)
    ex = np.delete(d, srt[-10:]).mean() * 1e4
    print(f"{k:10s} {1e4*r.mean():+8.1f}  {1e4*r.mean():+9.2f}  {1e4*m:+8.2f}  {t:+6.2f}  {y1:+7.2f} {y2:+7.2f}  {ex:+8.2f}  {100*(np.abs(d) > 1e-12).mean():5.1f}")
rnd = T["rnd"]
pf = TR[:, keys.index("PF10")]
print(f"PF10 vs random-delay control (same delay distribution, 20 perms): PF10 {1e4*pf.mean():+.1f} bps; "
      f"control mean {1e4*rnd.mean():+.1f} [{1e4*rnd.mean(1).min():+.1f} .. {1e4*rnd.mean(1).max():+.1f}]")
print(f"median hold bars {np.median(meta[:,1]):.0f}; PF10 median exit bar {np.median(meta[:,2]):.0f}; "
      f"PT median {np.median(meta[:,3]):.0f}; T10 median {np.median(meta[:,4]):.0f}")
print("net at 15 bps/side: subtract 30 bps = $30/trade from every row (exit choice does not add legs)")

print("\n== C. held-position states (every 5 printed bars): remaining return from NEXT open ==")
# S: 0 di,1 p10,2 p30,3 gain,4 dd,5 o_next,6 to_flat,7 next15
for lab, s in (("all", np.ones(len(S), bool)),
               ("in profit >5%", S[:, 3] > 0.05),
               ("flat +-5%", np.abs(S[:, 3]) <= 0.05),
               ("loss < -5%", S[:, 3] < -0.05),
               ("near peak dd>-3%", S[:, 4] > -0.03),
               ("off peak dd -3..-10%", (S[:, 4] <= -0.03) & (S[:, 4] > -0.10)),
               ("deep dd < -10%", S[:, 4] <= -0.10)):
    out = []
    for lo, hi in ((-1.01, -0.3), (-0.3, 0.3), (0.3, 1.01)):
        z = s & (S[:, 1] >= lo) & (S[:, 1] < hi)
        out.append((z.sum(), 1e4 * W(S[z, 6]).mean(), 1e4 * W(S[z, 7]).mean()))
    lo_ = s & (S[:, 1] < -0.3)
    hi_ = s & (S[:, 1] >= 0.3)
    # day-clustered difference in to-flat return, neg-pressure minus rest
    rest = s & ~lo_
    dl = np.bincount(S[lo_, 0].astype(int), W(S[lo_, 6]), NDAY) / np.maximum(np.bincount(S[lo_, 0].astype(int), minlength=NDAY), 1)
    dr = np.bincount(S[rest, 0].astype(int), W(S[rest, 6]), NDAY) / np.maximum(np.bincount(S[rest, 0].astype(int), minlength=NDAY), 1)
    both = (np.bincount(S[lo_, 0].astype(int), minlength=NDAY) > 0) & (np.bincount(S[rest, 0].astype(int), minlength=NDAY) > 0)
    d = (dl - dr)[both]
    print(f"{lab:22s} " + " | ".join(f"n={n:6d} flat {a:+6.1f} n15 {b:+6.1f}" for n, a, b in out) +
          f" || neg-rest toflat {1e4*d.mean():+.1f} t={d.mean()/(d.std(ddof=1)/np.sqrt(len(d))):+.2f}")
