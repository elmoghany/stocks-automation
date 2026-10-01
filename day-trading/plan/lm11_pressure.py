"""LEGACY-11: what does the champion's 30-bar "pressure" actually predict?

Pressure (day-trading.py Candles.pressure) = sum v*CLV / sum v over the
last n PRINTED bars, CLV = (2(c-l)-(h-l))/(h-l). Volume-weighted close
location. min_vol 20k shares else None.

Honest frame: cp_panel (466 sessions, fixed 04:00-16:00 grid, coverage
complete for the REGULAR-SESSION +10% close-cross universe, see cp_lib).
Hygiene: ^Z[A-Z]ZZT$ test symbols out, first RTH open > 3x prev_close
(reverse-split artefacts) out, price >= $2.

PART A (cross-section / time-series): at decision minutes 09:45..14:30
every 5 min, names that have closed >= +10% in RTH by m and are ACTIVE
(>= 20 printed of the last 30 minutes). Features use bars <= m only.
Forward return from the OPEN of bar m+1 (the first tradable print after
the decision; kills the close-location bid/ask bounce) to last close at
m+h, h = 1/5/15/30. Also forward range (vol) over the horizon.

PART B (exit): every first RTH +10% close-cross in 09:35..14:00, enter
at the next printed bar's open, flatten at last close <= 14:59. Exit
rules evaluated on the printed-bar path with state known at bar k-1
deciding bar k; stops fill at min(stop, open) (gap-through honest).

    python plan/lm11_pressure.py > scratch/lm11.log
"""
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cp_lib as L  # noqa: E402

TEST = re.compile(r"^Z[A-Z]ZZT$")
M_OPEN = 330
DEC = list(range(345, 631, 5))          # 09:45 .. 14:30
HOR = (1, 5, 15, 30)
M_FLAT = 659                             # 14:59
RNG = np.random.default_rng(11)


def pressure_grid(D, n, min_vol=20_000.0):
    """P[i, m] = Candles.pressure over the last n PRINTED bars ending at
    the last printed bar <= m; NaN when untrusted. Strictly causal."""
    out = np.full((D.n, L.NMIN), np.nan)
    rng = D.h - D.l
    with np.errstate(divide="ignore", invalid="ignore"):
        pos = np.where(rng > 0, (2 * (D.c - D.l) - rng) / rng, 0.0)
    for i in range(D.n):
        idx = np.flatnonzero(D.printed[i])
        if len(idx) == 0:
            continue
        v = D.v[i, idx]
        sv = v * np.nan_to_num(pos[i, idx])
        cv = np.concatenate([[0.0], np.cumsum(v)])
        csv = np.concatenate([[0.0], np.cumsum(sv)])
        k = np.arange(1, len(idx) + 1)
        j = np.maximum(0, k - n)
        vol = cv[k] - cv[j]
        with np.errstate(divide="ignore", invalid="ignore"):
            p = np.where(vol >= min_vol, (csv[k] - csv[j]) / vol, np.nan)
        # map to minutes: value at last printed bar <= m
        pos_m = np.searchsorted(idx, np.arange(L.NMIN), side="right") - 1
        ok = pos_m >= 0
        out[i, ok] = p[pos_m[ok]]
    return out


def day_rows(date):
    D = L.load_day(date)
    if D is None:
        return None, None, None
    keep = np.array([not TEST.match(s) for s in D.syms]) & (D.pc > 0)
    # reverse-split artefact: first RTH open > 3x prev close
    fo = np.full(D.n, np.nan)
    for i in range(D.n):
        r = np.flatnonzero(D.printed[i, M_OPEN:])
        if len(r):
            fo[i] = D.o[i, M_OPEN + r[0]]
    keep &= ~(fo > 3 * D.pc)
    P10 = pressure_grid(D, 10)
    P30 = pressure_grid(D, 30)
    last = D.last
    cnt = D.cumn
    c_rth = np.where(D.printed, D.c, -np.inf).copy()
    c_rth[:, :M_OPEN] = -np.inf
    crossed = np.maximum.accumulate(c_rth, axis=1) >= (1.10 * D.pc)[:, None]
    rows = []
    for m in DEC:
        act = (cnt[:, m] - cnt[:, m - 30]) >= 20
        u = keep & crossed[:, m] & act & (last[:, m] >= 2) & np.isfinite(P30[:, m])
        u &= D.printed[:, m + 1]
        ii = np.flatnonzero(u)
        if len(ii) == 0:
            continue
        ref = D.o[ii, m + 1]
        f = {}
        for h in HOR:
            f[h] = last[ii, m + h] / ref - 1
            hh = np.nanmax(np.where(D.printed[ii, m + 1:m + h + 1], D.h[ii, m + 1:m + h + 1], np.nan), axis=1)
            ll = np.nanmin(np.where(D.printed[ii, m + 1:m + h + 1], D.l[ii, m + 1:m + h + 1], np.nan), axis=1)
            f["r%d" % h] = (hh - ll) / ref
        ret30 = last[ii, m] / last[ii, m - 30] - 1
        ret5 = last[ii, m] / last[ii, m - 5] - 1
        # realised vol of the PAST 30 minutes (for the vol-forecast control)
        ph = np.nanmax(np.where(D.printed[ii, m - 29:m + 1], D.h[ii, m - 29:m + 1], np.nan), axis=1)
        pl = np.nanmin(np.where(D.printed[ii, m - 29:m + 1], D.l[ii, m - 29:m + 1], np.nan), axis=1)
        prng = (ph - pl) / last[ii, m]
        bounce = last[ii, m] / ref - 1  # close(m) vs open(m+1)
        for q, i in enumerate(ii):
            rows.append((m, P10[i, m], P30[i, m], ret30[q], ret5[q], prng[q],
                         bounce[q], *[f[h][q] for h in HOR], *[f["r%d" % h][q] for h in HOR]))
    A = np.array(rows, dtype=float) if rows else None

    # ---- PART B: trades ----
    trades = []
    states = []
    cm = D.cross_minute(mode="LAST", start=M_OPEN, end=600)
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
        o, h, l, c = D.o[i, pr], D.h[i, pr], D.l[i, pr], D.c[i, pr]
        p10 = P10[i, pr]
        p30 = P30[i, pr]
        flat = c[-1]
        res = {"H": flat / ent - 1}
        peak_prev = np.concatenate([[ent], np.maximum.accumulate(np.maximum(h, ent))[:-1]])
        p10_prev = np.concatenate([[P10[i, e - 1]], p10[:-1]])

        def trail(width):
            stop = peak_prev * (1 - width)
            hit = np.flatnonzero(l <= stop)
            hit = hit[hit >= 1] if len(hit) else hit
            if len(hit) == 0:
                return flat / ent - 1, len(pr) - 1
            k = hit[0]
            return min(stop[k], o[k]) / ent - 1, k

        def w_ptrail(lo_w, hi_w, inv=False):
            w = np.full(len(pr), np.inf)
            neg = p10_prev <= -0.3
            pos = p10_prev >= 0.3
            if inv:
                neg, pos = pos, neg
            w[neg] = lo_w
            w[pos] = hi_w
            return w

        res["T10"], kT10 = trail(0.10)
        res["T20"], _ = trail(0.20)
        res["PT"], kPT = trail(w_ptrail(0.10, 0.40))
        res["PTinv"], _ = trail(w_ptrail(0.10, 0.40, inv=True))
        res["PT10only"], _ = trail(w_ptrail(0.10, np.inf))

        def flip(arr, thr, ge=False, min_k=5):
            cond = (arr >= thr) if ge else (arr <= thr)
            cond[:min_k] = False
            cond[-1] = False
            k = np.flatnonzero(cond)
            if len(k) == 0:
                return flat / ent - 1, len(pr) - 1
            return o[k[0] + 1] / ent - 1, k[0] + 1

        res["PF10"], kPF10 = flip(p10.copy(), -0.3)
        res["PF30"], kPF30 = flip(p30.copy(), -0.3)
        res["PF10inv"], _ = flip(p10.copy(), 0.3, ge=True)
        # flip only once in profit (the champion's 'profit' pressure_exit)
        gain = c / ent - 1
        cond = (p10 <= -0.3) & (gain > 0.05)
        cond[:5] = False
        cond[-1] = False
        kk = np.flatnonzero(cond)
        res["PFprof"] = (o[kk[0] + 1] / ent - 1) if len(kk) else flat / ent - 1
        trades.append((date, i, e, pr[-1] - e, res, pr, o, kPF10, kPT, kT10))
        # held-position states every 5 printed bars
        runpk = np.maximum.accumulate(h)
        for k in range(5, len(pr) - 2, 5):
            states.append((p10[k], p30[k], c[k] / ent - 1, c[k] / runpk[k] - 1,
                           o[k + 1], flat / o[k + 1] - 1,
                           (o[min(k + 16, len(pr) - 1)] / o[k + 1] - 1)))
    return A, trades, states


def main():
    dates = L.panel_dates()
    import os
    if os.environ.get('LM11_N'):
        dates = dates[:int(os.environ['LM11_N'])]
    allA, allT, allS, dlab = [], [], [], []
    for di, d in enumerate(dates):
        A, T, S = day_rows(d)
        if A is not None:
            allA.append(np.column_stack([np.full(len(A), di), A]))
        allT += T or []
        allS += [(di,) + s for s in (S or [])]
        if di % 50 == 0:
            print("day", di, d, flush=True)
    A = np.vstack(allA)
    np.save(Path(sys.argv[1]) / "lm11_A.npy", A)
    S = np.array(allS, dtype=float)
    np.save(Path(sys.argv[1]) / "lm11_S.npy", S)
    import pickle
    keys = list(allT[0][4].keys())
    TR = np.array([[t[4][k] for k in keys] for t in allT])
    meta = np.array([(dates.index(t[0]), t[3], t[7], t[8], t[9]) for t in allT])
    # random-delay control for PF10: shuffle exit delays across trades
    rnd = []
    delays = meta[:, 2].astype(int)
    for rep in range(20):
        perm = RNG.permutation(len(allT))
        r = []
        for q, t in enumerate(allT):
            pr, o = t[5], t[6]
            k = min(delays[perm[q]], len(pr) - 1)
            r.append(o[k] / o[0] - 1 if k < len(pr) - 1 else TR[q, keys.index("H")])
        rnd.append(r)
    with open(Path(sys.argv[1]) / "lm11_T.pkl", "wb") as fh:
        pickle.dump(dict(keys=keys, TR=TR, meta=meta, rnd=np.array(rnd), dates=dates), fh)
    print("rows", A.shape, "trades", TR.shape, "states", S.shape)


if __name__ == "__main__":
    main()
