"""SWING-REVERSION adversarial check: is the 5-day-loser edge just
exposure to high-volatility names?  Vol-matched control: on each signal
day, replace every loser pick with a random top-K name drawn from the same
trailing-20d-volatility quintile (computed <= signal day), same entry/exit
dates. 30 seeds.  python plan/sr_volmatch.py gd|long"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sr_run as R  # noqa: E402
from sr_lib import simulate  # noqa: E402

P, F, C, U = R.P, R.F, R.C, R.U
O = P["O"].values
Cv = C.values
lastc = pd.DataFrame(Cv).ffill().values
vol = (C / C.shift(1) - 1).rolling(20, min_periods=18).std()
rk = F["dv20"].where(U).rank(axis=1, ascending=False)
for K, H, n in ((500, 3, 5), (500, 5, 5), (500, 5, 10), (300, 5, 10)):
    UK = U & (rk <= K)
    if R.DS == "long":
        UK = U
    size = 100_000 / n
    tr, _ = simulate(P, F["ret5"].where(UK), None, H, n, size, R.C6, start=R.START, end=R.END)
    vq = vol.where(UK).rank(axis=1, pct=True).values
    UKv = UK.values
    ctl = np.zeros((30, len(tr)))
    for sd in range(30):
        rng = np.random.default_rng(77 + sd)
        for k, r in enumerate(tr.itertuples()):
            s = r.sig_t
            q = vq[s, r.j]
            if not np.isfinite(q):
                continue
            lo, hi = np.floor(q * 5) / 5, np.floor(q * 5) / 5 + 0.2
            cand = np.where(UKv[s] & (vq[s] >= lo) & (vq[s] <= hi + 1e-9) & np.isfinite(O[r.ent_t]))[0]
            if not len(cand):
                continue
            j = cand[rng.integers(len(cand))]
            pout = O[r.ex_t, j] if r.kind == "x" else lastc[r.ex_t, j]
            if not np.isfinite(pout):
                pout = lastc[r.ex_t - 1, j]
            g = pout / O[r.ent_t, j] - 1
            ctl[sd, k] = size * g - R.C6 * size * (2 + g)
    out = []
    for sp, (a, b, mo) in R.SPLITS.items():
        m = ((tr.ent_date >= pd.Timestamp(a)) & (tr.ent_date <= pd.Timestamp(b))).values
        s_mo = tr.pnl[m].sum() / mo
        c_mo = ctl[:, m].sum(axis=1) / mo
        out.append(f"{sp}: strat {s_mo:+7.0f} volctl {c_mo.mean():+7.0f} pct {100 * (c_mo < s_mo).mean():3.0f}")
    tot = tr.pnl.sum()
    print(f"K{K} H{H} N{n}: " + " | ".join(out) + f" | ALL pct {100 * (ctl.sum(axis=1) < tot).mean():.0f}", flush=True)
print("DONE")
