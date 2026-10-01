"""LEGACY-11 part B2: does pressure help a TRAIL decide WHEN to fire?

Same trade set as lm11_pressure.py part B (every first RTH +10% close-cross
09:35..14:00, hygiene, enter next printed open, flatten last close <= 14:59).
State known at bar k-1 decides bar k. Intrabar stops fill min(stop, open).

  H        hold to flatten
  T10/T15/T20   plain trail from peak HIGH since entry
  T10S/T20S     same trail, SUSPENDED while P10(k-1) <= -0.3 (no sell into a
                one-sided sell tape; fires later if the level is still breached)
  T10N/T20N     control: trail ARMED ONLY while P10(k-1) <= -0.3 (champion's leg)
  C10/C20       close-based: close(k) <= peak*(1-w) -> sell next open
  C10S/C20S     close-based, skipped when P10(k) <= -0.3
  C10N/C20N     close-based, only when P10(k) <= -0.3 (inverse control)
    python plan/lm11_exit2.py <outdir>
"""
import os, re, sys, pickle
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
import cp_lib as L
from lm11_pressure import pressure_grid, TEST, M_OPEN, M_FLAT

def run_day(date):
    D = L.load_day(date)
    keep = np.array([not TEST.match(s) for s in D.syms]) & (D.pc > 0)
    fo = np.full(D.n, np.nan)
    for i in range(D.n):
        r = np.flatnonzero(D.printed[i, M_OPEN:])
        if len(r):
            fo[i] = D.o[i, M_OPEN + r[0]]
    keep &= ~(fo > 3 * D.pc)
    P10 = pressure_grid(D, 10)
    cnt = D.cumn
    cm = D.cross_minute(mode="LAST", start=M_OPEN, end=600)
    out = []
    for i in np.flatnonzero(keep & (cm < L.NMIN)):
        sig = max(int(cm[i]), 334)
        pr = np.flatnonzero(D.printed[i, sig + 1:M_FLAT + 1]) + sig + 1
        if len(pr) < 10 or pr[0] > sig + 5:
            continue
        e = pr[0]
        if (cnt[i, e - 1] - cnt[i, max(e - 31, 0)]) < 10:
            continue
        ent = D.o[i, e]
        if not (ent >= 2):
            continue
        dv30 = float(np.nansum(D.c[i, e - 30:e] * D.v[i, e - 30:e]))
        o, h, l, c = D.o[i, pr], D.h[i, pr], D.l[i, pr], D.c[i, pr]
        p = P10[i, pr]
        pprev = np.concatenate([[P10[i, e - 1]], p[:-1]])
        flat = c[-1]
        pk = np.maximum.accumulate(np.maximum(h, ent))
        pkprev = np.concatenate([[ent], pk[:-1]])
        neg_prev = pprev <= -0.3          # NaN -> False
        neg = p <= -0.3
        r = {"H": flat / ent - 1}
        for w in (0.10, 0.15, 0.20):
            stop = pkprev * (1 - w)
            for tag, arm in (("", np.ones(len(pr), bool)), ("S", ~neg_prev), ("N", neg_prev)):
                if w == 0.15 and tag:
                    continue
                hit = np.flatnonzero((l <= stop) & arm)
                hit = hit[hit >= 1]
                r[f"T{int(w*100)}{tag}"] = (min(stop[hit[0]], o[hit[0]]) / ent - 1) if len(hit) else flat / ent - 1
            if w == 0.15:
                continue
            for tag, arm in (("", np.ones(len(pr), bool)), ("S", ~neg), ("N", neg)):
                cond = (c <= pk * (1 - w)) & arm
                cond[-1] = False
                k = np.flatnonzero(cond)
                r[f"C{int(w*100)}{tag}"] = (o[k[0] + 1] / ent - 1) if len(k) else flat / ent - 1
        out.append((e, dv30, r))
    return out

def main():
    dates = L.panel_dates()
    if os.environ.get("LM11_N"):
        dates = dates[:int(os.environ["LM11_N"])]
    rows = []
    for di, d in enumerate(dates):
        for e, dv, r in run_day(d):
            rows.append((di, e, dv, r))
        if di % 100 == 0:
            print("day", di, flush=True)
    keys = list(rows[0][3].keys())
    M = np.array([(a, b, c) for a, b, c, _ in rows])
    R = np.array([[x[3][k] for k in keys] for x in rows])
    pickle.dump(dict(keys=keys, M=M, R=R, ndays=len(dates)), open(Path(sys.argv[1]) / "lm11_B2.pkl", "wb"))
    print("done", R.shape)

if __name__ == "__main__":
    main()
