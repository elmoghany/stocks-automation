"""SWING-REVERSION: beta / alpha / Sharpe of the daily MTM curve vs SPY
buy-and-hold ($100k), per split.  python plan/sr_beta.py gd|long"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sr_run as R  # noqa: E402
from sr_lib import simulate  # noqa: E402

F, U, C = R.F, R.U, R.C
rk = F["dv20"].where(U).rank(axis=1, ascending=False)
UK = U & (rk <= 500)
spy = C["SPY"]
cfg = {"LOSER5d|top500|H3|N5": (F["ret5"].where(UK), None, 3, 5),
       "LOSER5d|top500|H5|N5": (F["ret5"].where(UK), None, 5, 5),
       "LOSER5d|top500|H5|N10": (F["ret5"].where(UK), None, 5, 10),
       "MR-rsi2<5|ma200|x>ma5|H10|N10": R.STRATS["MR-rsi2<5|ma200|x>ma5|H10"][:3] + (10,)}
for name, (S, X, H, n) in cfg.items():
    tr, cur = simulate(R.P, S, X, H, n, 100_000 / n, R.C6, start=R.START, end=R.END)
    d = cur.diff()
    sd = 100_000 * spy.pct_change()
    out = []
    for sp, (a, b, mo) in R.SPLITS.items():
        m = (d.index >= pd.Timestamp(a)) & (d.index <= pd.Timestamp(b)) & d.notna() & sd.notna()
        y, x = d[m].values, sd[m].values
        beta = np.cov(y, x)[0, 1] / np.var(x)
        alpha_mo = (y - beta * x).mean() * 21
        sh = y.mean() / y.std() * np.sqrt(252)
        shs = x.mean() / x.std() * np.sqrt(252)
        out.append(f"{sp}: beta {beta:.2f} alpha/mo {alpha_mo:+6.0f} Sharpe {sh:.2f} (SPY {shs:.2f})")
    print(f"{name:32s} " + " | ".join(out), flush=True)
