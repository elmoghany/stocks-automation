"""SWING-REVERSION library: panel, features, portfolio engine, controls.

Engine conventions (honest default, mode="open"):
  * signal computed on CLOSE of day s (all inputs <= s)
  * entry at OPEN of s+1 (first price available after the signal)
  * exit condition evaluated on close t (inputs <= t) -> sell at OPEN t+1
  * time stop H = max number of closes held; sell at the next open
  * delisting / data stop: position closed at the last available close
mode="close" (labelled OPTIMISTIC): enter at close s, exit at close t -- a
  Connors-style MOC approximation that needs the signal computed from a
  ~15:55 print; reported only as a sensitivity.
Ranking: lower score = better; ties broken by seeded random jitter.
P&L: fixed $ per position (no compounding), cost per side on notional.
"""
import numpy as np
import pandas as pd


# ---------------------------------------------------------------- features
def rsi(C, n):
    d = C.diff()
    up = d.clip(lower=0)
    dn = (-d).clip(lower=0)
    au = up.ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()
    ad = dn.ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()
    r = 100 - 100 / (1 + au / ad.replace(0, np.nan))
    r = r.where(ad > 0, 100.0)
    return r.where(C.notna())


def features(P):
    C, O, H, L, V = P["C"], P["O"], P["H"], P["L"], P["V"]
    F = {}
    F["rsi2"] = rsi(C, 2)
    F["rsi3"] = rsi(C, 3)
    for n in (5, 10, 20, 50, 100, 200):
        F[f"ma{n}"] = C.rolling(n, min_periods=n).mean()
    sd20 = C.rolling(20, min_periods=20).std()
    F["bbl"] = F["ma20"] - 2 * sd20
    dn = (C < C.shift(1)).astype(float).where(C.notna() & C.shift(1).notna())
    # consecutive down closes
    run = np.zeros(C.shape)
    a = dn.fillna(0).values
    for i in range(1, len(a)):
        run[i] = np.where(a[i] > 0, run[i - 1] + 1, 0)
    F["downrun"] = pd.DataFrame(run, index=C.index, columns=C.columns)
    F["low10"] = C.rolling(10, min_periods=10).min()
    F["ret1"] = C / C.shift(1) - 1
    F["ret5"] = C / C.shift(5) - 1
    F["hh120"] = H.shift(1).rolling(120, min_periods=120).max()
    F["hh252"] = H.shift(1).rolling(252, min_periods=252).max()
    dv = C * V
    F["dv20"] = dv.rolling(20, min_periods=18).median()
    F["vol20"] = V.shift(1).rolling(20, min_periods=18).mean()
    F["gap"] = O / C.shift(1) - 1
    return F


# ---------------------------------------------------------------- engine
def simulate(P, S, X, H, nslots, size, cost, mode="open", seed=0, start=None,
             end=None):
    """S: DataFrame score (NaN = no signal). X: DataFrame bool exit flag
    (evaluated at close) or None. H: time stop in closes."""
    dates = P["C"].index
    O = P["O"].values
    C = P["C"].values
    Sv = S.values
    Xv = X.values if X is not None else np.zeros(C.shape, bool)
    T, N = C.shape
    rng = np.random.default_rng(seed)
    jit = rng.random(Sv.shape) * 1e-9
    last_c = pd.DataFrame(C).ffill().values
    t0 = 0 if start is None else int(np.searchsorted(dates, pd.Timestamp(start)))
    t1 = T if end is None else int(np.searchsorted(dates, pd.Timestamp(end), "right"))
    pos = {}  # j -> [entry_t, entry_px, held, pending, sig_t]
    trades = []
    eq_real = 0.0
    curve = np.full(T, np.nan)

    def close_pos(j, t, px, kind):
        nonlocal eq_real
        e = pos.pop(j)
        g = px / e[1] - 1
        pnl = size * g - cost * size * (2 + g)
        eq_real += pnl
        trades.append((e[4], e[0], t, j, e[1], px, g, pnl, e[2], kind))

    for t in range(max(t0, 1), t1):
        if mode == "open":
            # exits at open t
            for j in [j for j, e in pos.items() if e[3]]:
                px = O[t, j]
                if not np.isfinite(px):
                    px = last_c[t - 1, j]
                close_pos(j, t, px, "x")
            # entries at open t from signals at close t-1
            free = nslots - len(pos)
            if free > 0 and t - 1 >= t0:
                s = Sv[t - 1] + jit[t - 1]
                ok = np.isfinite(s) & np.isfinite(O[t])
                if ok.any():
                    idx = np.where(ok)[0]
                    idx = idx[np.argsort(s[idx])]
                    for j in idx:
                        if free == 0:
                            break
                        if j in pos:
                            continue
                        pos[j] = [t, O[t, j], 0, False, t - 1]
                        free -= 1
            # close-of-day bookkeeping
            for j, e in list(pos.items()):
                if not np.isfinite(C[t, j]):
                    # missing print today: if no later data at all -> delisted
                    if not np.isfinite(C[t:, j]).any():
                        close_pos(j, t, last_c[t, j], "delist")
                    continue
                e[2] += 1
                if e[2] >= H or Xv[t, j]:
                    e[3] = True
        else:  # close mode
            for j, e in list(pos.items()):
                if not np.isfinite(C[t, j]):
                    if not np.isfinite(C[t:, j]).any():
                        close_pos(j, t, last_c[t, j], "delist")
                    continue
                e[2] += 1
                if e[2] >= H or Xv[t, j]:
                    close_pos(j, t, C[t, j], "x")
            free = nslots - len(pos)
            if free > 0:
                s = Sv[t] + jit[t]
                ok = np.isfinite(s) & np.isfinite(C[t])
                idx = np.where(ok)[0]
                idx = idx[np.argsort(s[idx])]
                for j in idx:
                    if free == 0:
                        break
                    if j in pos:
                        continue
                    pos[j] = [t, C[t, j], 0, False, t]
                    free -= 1
        unreal = sum(size * (last_c[t, j] / e[1] - 1) for j, e in pos.items())
        curve[t] = eq_real + unreal
    # force-close anything open at the end (mark at last close)
    for j in list(pos):
        close_pos(j, t1 - 1, last_c[t1 - 1, j], "end")
    tr = pd.DataFrame(trades, columns=["sig_t", "ent_t", "ex_t", "j", "px_in",
                                       "px_out", "g", "pnl", "held", "kind"])
    tr["ent_date"] = dates[tr.ent_t.values] if len(tr) else []
    tr["ticker"] = P["C"].columns[tr.j.values] if len(tr) else []
    return tr, pd.Series(curve, index=dates)


def random_control(P, U, tr, size, cost, seeds=30, mode="open"):
    """Same entry/exit dates & sizes as `tr`, ticker replaced by a random
    member of universe U on the signal day. Returns DataFrame seeds x trades
    pnl (so any split can be summed)."""
    O = P["O"].values
    C = P["C"].values
    last_c = pd.DataFrame(C).ffill().values
    Uv = U.values
    out = np.zeros((seeds, len(tr)))
    members = {}
    for k, (s, e, x) in enumerate(zip(tr.sig_t.values, tr.ent_t.values, tr.ex_t.values)):
        if s not in members:
            pin = O[e] if mode == "open" else C[e]
            members[s] = np.where(Uv[s] & np.isfinite(pin))[0]
    for sd in range(seeds):
        rng = np.random.default_rng(1000 + sd)
        for k, (s, e, x, kind) in enumerate(zip(tr.sig_t.values, tr.ent_t.values,
                                                 tr.ex_t.values, tr.kind.values)):
            m = members[s]
            if len(m) == 0:
                continue
            j = m[rng.integers(len(m))]
            pin = O[e, j] if mode == "open" else C[e, j]
            if mode == "open" and kind == "x":
                pout = O[x, j]
                if not np.isfinite(pout):
                    pout = last_c[x - 1, j]
            else:
                pout = C[x, j] if np.isfinite(C[x, j]) else last_c[x, j]
            g = pout / pin - 1
            out[sd, k] = size * g - cost * size * (2 + g)
    return out


def stats(tr, curve, dates_lo, dates_hi, months, size, cost_adj=None):
    m = (tr.ent_date >= pd.Timestamp(dates_lo)) & (tr.ent_date <= pd.Timestamp(dates_hi))
    t = tr[m]
    pnl = t.pnl if cost_adj is None else cost_adj(t)
    n = len(t)
    c = curve[(curve.index >= pd.Timestamp(dates_lo)) & (curve.index <= pd.Timestamp(dates_hi))].dropna()
    dd = float((c - c.cummax()).min()) if len(c) else 0.0
    top5 = pnl.sort_values(ascending=False).head(5).sum() if n else 0.0
    return dict(n=n, per_tr=float(pnl.mean()) if n else 0.0,
                tr_mo=n / months, mo=float(pnl.sum()) / months,
                win=float((pnl > 0).mean()) if n else 0.0,
                maxdd=dd, ex5_mo=float(pnl.sum() - top5) / months,
                hold=float(t.held.mean()) if n else 0.0)
