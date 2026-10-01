"""LEGACY-11 part B3: pressure-gated TAKE-PROFIT (sell an extended winner into
non-negative pressure, hold it through a wash-out).  Rules (close-based, sell next open):
  TPx    close >= entry*(1+x)                    (plain target, control)
  TPxP   close >= entry*(1+x) AND P10 > -0.3     (champion-inverse: do not sell a washout)
  TPxN   close >= entry*(1+x) AND P10 <= -0.3    (inverse control)
  +T10   each of the above combined with the plain 10% high-trail
(derived from B2; original B2 doc follows)


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
        stop = pkprev * 0.90
        th = np.flatnonzero(l <= stop); th = th[th >= 1]
        kt = th[0] if len(th) else None
        r["T10"] = (min(stop[kt], o[kt]) / ent - 1) if kt is not None else flat / ent - 1
        for x in (0.05, 0.10, 0.15, 0.25):
            for tag, arm in (("", np.ones(len(pr), bool)), ("P", ~neg), ("N", neg)):
                cond = (c >= ent * (1 + x)) & arm
                cond[-1] = False
                k = np.flatnonzero(cond)
                kp = k[0] + 1 if len(k) else None
                r[f"TP{int(x*100)}{tag}"] = (o[kp] / ent - 1) if kp is not None else flat / ent - 1
                # combined with T10: whichever fires first
                if kt is not None and (kp is None or kt <= kp):
                    r[f"TP{int(x*100)}{tag}+T10"] = r["T10"]
                else:
                    r[f"TP{int(x*100)}{tag}+T10"] = r[f"TP{int(x*100)}{tag}"]
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
    pickle.dump(dict(keys=keys, M=M, R=R, ndays=len(dates)), open(Path(sys.argv[1]) / "lm11_B3.pkl", "wb"))
    print("done", R.shape)

if __name__ == "__main__":
    main()
