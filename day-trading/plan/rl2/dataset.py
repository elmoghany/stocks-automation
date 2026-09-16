"""RL-SERIES v2 (2026-09-16): the flat row table.

One row = one (date, decision step, symbol) at which a ticket could have
been opened -- i.e. bar m PRINTED. Rows carry the causal feature vector
(plan/rl2/features.py) and the realized net return of the trade a decision
there would open, at every horizon.

Cached as plan/rl2/out/rows.npz. The cache is ~1 GB and is rebuilt in a
few minutes from plan/rl2/out/feat/.
"""
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import features as FT                                         # noqa: E402

FEAT = HERE / "out" / "feat"
CACHE = HERE / "out" / "rows.npz"


def build(force=False):
    if CACHE.exists() and not force:
        return
    files = sorted(FEAT.glob("*.npz"))
    X, Y, OKY, D, TT, SS, MRK = [], [], [], [], [], [], []
    syms_all = []
    sym_id = {}
    for di, p in enumerate(files):
        z = np.load(p, allow_pickle=False)
        F, prn, tgt, ok = z["F"], z["printed"], z["tgt"], z["tgt_ok"]
        t_i, s_i = np.nonzero(prn)
        if not len(t_i):
            continue
        X.append(F[t_i, s_i])
        Y.append(tgt[t_i, s_i])
        OKY.append(ok[t_i, s_i])
        D.append(np.full(len(t_i), di, np.int32))
        TT.append(t_i.astype(np.int16))
        ids = []
        for s in z["syms"]:
            s = str(s)
            if s not in sym_id:
                sym_id[s] = len(sym_id)
                syms_all.append(s)
            ids.append(sym_id[s])
        SS.append(np.asarray(ids, np.int32)[s_i])
        MRK.append(z["mark"][t_i, s_i])
    np.savez(CACHE, X=np.concatenate(X), Y=np.concatenate(Y),
             OKY=np.concatenate(OKY), D=np.concatenate(D),
             T=np.concatenate(TT), S=np.concatenate(SS),
             MARK=np.concatenate(MRK),
             dates=np.array([p.stem for p in files]),
             syms=np.array(syms_all))
    print(f"rows: {sum(len(x) for x in X):,} over {len(files)} days, "
          f"{len(syms_all):,} distinct symbols -> {CACHE}", flush=True)


class Rows:
    def __init__(self):
        build()
        z = np.load(CACHE, allow_pickle=False)
        self.X = z["X"]
        self.Y = z["Y"]
        self.OKY = z["OKY"]
        self.D = z["D"]
        self.T = z["T"]
        self.S = z["S"]
        self.MARK = z["MARK"]
        self.dates = [str(d) for d in z["dates"]]
        self.syms = [str(s) for s in z["syms"]]
        self.date_of_row = np.array(self.dates)[self.D]

    def mask_dates(self, lo, hi):
        """rows with lo <= date < hi (string compare on ISO dates)."""
        return (self.date_of_row >= lo) & (self.date_of_row < hi)


if __name__ == "__main__":
    build(force="--force" in sys.argv)
