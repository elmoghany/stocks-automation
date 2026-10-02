"""SWING-REVERSION adversarial audit of the best-looking rule
(daily 5-day-loser reversal in the top-K liquid names).

python plan/sr_robust.py gd|long
  * neighbourhood grid: K (top-K by 20d median $vol), loser threshold
    (cross-sectional percentile of 5-day return), hold H, slots N
  * ordering audit: rank-by-ret5 vs RANDOM order among qualifiers (30 seeds)
  * excess vs SPY over each trade's exact holding window ($/trade)
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sr_run as R  # noqa: E402  (builds panel, universe, features on import)
from sr_lib import simulate  # noqa: E402

P, F, C, U, SPLITS = R.P, R.F, R.C, R.U, R.SPLITS
spyO = P["O"]["SPY"].values if "SPY" in C.columns else None
spyC = P["C"]["SPY"].values if "SPY" in C.columns else None
rk = F["dv20"].where(U).rank(axis=1, ascending=False)


def excess(tr, mode="open"):
    if spyO is None or not len(tr):
        return np.zeros(len(tr))
    a = spyO[tr.ent_t.values] if mode == "open" else spyC[tr.ent_t.values]
    b = np.where(tr.kind.values == "x", spyO[tr.ex_t.values], spyC[tr.ex_t.values]) if mode == "open" else spyC[tr.ex_t.values]
    return tr.g.values - (b / a - 1)


def split_mo(tr, size, cost=R.C6, col="g"):
    out = {}
    for sp, (a, b, mo) in SPLITS.items():
        m = (tr.ent_date >= pd.Timestamp(a)) & (tr.ent_date <= pd.Timestamp(b))
        g = tr.loc[m, col]
        out[sp] = float((size * g - cost * size * (2 + g)).sum()) / mo
    return out


rows = []
for K in (300, 500, 1000):
    UK = U & (rk <= K)
    for q in (0.02, 0.05, 0.10):
        pq = F["ret5"].where(UK).quantile(q, axis=1)
        sig = UK & F["ret5"].le(pq, axis=0)
        for H in (3, 5, 10):
            for n in (5, 10):
                size = 100_000 / n
                tr, cur = simulate(P, F["ret5"].where(sig), None, H, n, size, R.C6, start=R.START, end=R.END)
                tr["xs"] = excess(tr)
                m = split_mo(tr, size)
                x = split_mo(tr, size, cost=0.0, col="xs")
                rows.append(dict(K=K, q=q, H=H, N=n, ntr=len(tr), **{f"{k}": round(v) for k, v in m.items()},
                                 **{f"xs_{k}": round(v) for k, v in x.items()},
                                 ex5=round((tr.pnl.sum() - tr.pnl.nlargest(5).sum()) / sum(v[2] for v in SPLITS.values()))))
                print(rows[-1], flush=True)
G = pd.DataFrame(rows)
sp = list(SPLITS)
G["all_pos"] = (G[sp] > 0).all(axis=1)
G["xs_all_pos"] = (G[[f"xs_{s}" for s in sp]] > 0).all(axis=1)
print("\nGRID cells:", len(G), " all-splits-positive (6bps):", int(G.all_pos.sum()),
      " all-splits-positive EXCESS vs SPY (gross):", int(G.xs_all_pos.sum()))
print(G[sp].describe().round(0).to_string())

# ordering audit at the headline cell (K=500, q=0.05, H=5)
UK = U & (rk <= 500)
pq = F["ret5"].where(UK).quantile(0.05, axis=1)
sig = UK & F["ret5"].le(pq, axis=0)
for n in (5, 10):
    size = 100_000 / n
    res = []
    for sd in range(30):
        rnd = pd.DataFrame(np.random.default_rng(500 + sd).random(C.shape), index=C.index, columns=C.columns)
        tr, _ = simulate(P, rnd.where(sig), None, 5, n, size, R.C6, start=R.START, end=R.END)
        res.append(split_mo(tr, size))
    D = pd.DataFrame(res)
    print(f"\nRANDOM ORDER among qualifiers, N={n}: mean/min/max $/mo per split")
    print(D.agg(["mean", "min", "max"]).round(0).to_string())
    print("share of seeds positive in every split:", float((D > 0).all(axis=1).mean()))
G.to_csv(R.OUT / f"sr_robust_{R.DS}.csv", index=False)
print("DONE")
