"""Item 4: what predictive signal exists in AMD daily data? Simple checkable statistics, each split into 2013-Jul 2023 (early) and Aug 2023-Nov 11 2026 (recent).

Every signal is computed only from data up to the close of day t. The outcome is the forward log return from the OPEN of day t+1 (the fill price) to the close of day t+h.
Effects are differences in the mean forward return between the signal being on and off (or against the period's ordinary mean for events), with a t-statistic that allows for
overlapping windows (Newey-West, lag h). "Stable" = same sign and a t-statistic that is not tiny in both periods. A list of about 40 statistics is tested, so a lone t of 2 is expected by chance.
Nothing here is tuned: the lists were written before looking at results.
Part G at the end runs plain pre-listed in/out rules built from these signals, so the effect can be seen in dollars against held.
"""
import numpy as np
import pandas as pd
from common import *

f = load_amd()
o, c, idx = f.open.values, f.close.values, f.index
n = len(c)
W = windows(idx)
lc = np.log(c)
ret = np.r_[np.nan, np.diff(lc)]
qqq = load_etf("QQQ").reindex(idx, method="ffill")
smh = load_etf("SMH").reindex(idx, method="ffill")
qret = np.r_[np.nan, np.diff(np.log(qqq.close.values))]
sret = np.r_[np.nan, np.diff(np.log(smh.close.values))]
S = lambda a: pd.Series(a, index=idx)


def fwd(h):
    out = np.full(n, np.nan)
    for t in range(n - h):
        out[t] = lc[t + h] - np.log(o[t + 1])
    return out


FWD = {h: fwd(h) for h in (1, 5, 10, 21, 42, 63)}


def hac_diff(y, x, L):
    """OLS of y on [1, x]; returns slope (mean difference when x is 0/1) and its Newey-West t-statistic."""
    m = ~(np.isnan(y) | np.isnan(x))
    y, x = y[m], x[m].astype(float)
    if len(y) < 30 or x.std() == 0:
        return np.nan, np.nan, len(y)
    X = np.c_[np.ones(len(y)), x]
    beta = np.linalg.lstsq(X, y, rcond=None)[0]
    e = y - X @ beta
    Xe = X * e[:, None]
    Sg = Xe.T @ Xe
    for l in range(1, L + 1):
        w = 1 - l / (L + 1)
        G = Xe[l:].T @ Xe[:-l]
        Sg += w * (G + G.T)
    XtXi = np.linalg.inv(X.T @ X)
    V = XtXi @ Sg @ XtXi
    return beta[1], beta[1] / np.sqrt(V[1, 1]), len(y)


def period_mask(w, h):
    lo, hi = W[w]
    m = np.zeros(n, dtype=bool)
    top = hi - h - 1 if w == "early" else n - h - 1
    m[lo:top + 1] = True
    return m


def state_effect(name, state, hs=(1, 21), rows=None):
    """Mean forward return when state is on minus when off, per period and horizon, in percent, with t-stat."""
    state = np.asarray(state, dtype=float)
    for h in hs:
        row = {"signal": name, "h": h}
        for w in ("early", "recent"):
            m = period_mask(w, h)
            y = np.where(m, FWD[h], np.nan)
            x = np.where(m, state, np.nan)
            eff, t, cnt = hac_diff(y, x, h)
            on = np.nansum((x == 1) & m) / m.sum()
            row.update({f"{w}_effect_pct": 100 * (np.exp(eff) - 1) if not np.isnan(eff) else np.nan, f"{w}_t": t, f"{w}_share_on": on})
        rows.append(row)


def event_effect(name, ev, hs=(1, 5, 21), gap=21, rows=None):
    """Forward return after event days (declustered: no event within gap days after the previous one) against the ordinary mean of the same period."""
    ev = np.asarray(ev, dtype=bool)
    for h in hs:
        row = {"signal": name, "h": h}
        for w in ("early", "recent"):
            lo, hi = W[w]
            m = period_mask(w, h)
            days = [t for t in np.nonzero(ev & m)[0]]
            kept, last = [], -10_000
            for t in days:
                if t - last > gap:
                    kept.append(t)
                    last = t
            y = FWD[h][m]
            base = np.nanmean(y)
            ys = FWD[h][kept]
            if len(ys) >= 3:
                se = ys.std(ddof=1) / np.sqrt(len(ys))
                row.update({f"{w}_n": len(ys), f"{w}_mean_pct": 100 * (np.exp(ys.mean()) - 1), f"{w}_ordinary_pct": 100 * (np.exp(base) - 1), f"{w}_excess_pct": 100 * (ys.mean() - base), f"{w}_t": (ys.mean() - base) / se})
            else:
                row.update({f"{w}_n": len(ys)})
        rows.append(row)


def part_a():
    """Autocorrelation of daily returns and of multi-day returns."""
    rows = []
    for w in ("early", "recent"):
        lo, hi = W[w]
        r = ret[lo:hi]
        row = {"period": w, "days": hi - lo}
        for lag in (1, 2, 3, 5):
            row[f"daily_ac_lag{lag}"] = float(pd.Series(r).autocorr(lag))
        rows.append(row)
    A = pd.DataFrame(rows)
    rows = []
    for h in (5, 10, 21, 42, 63, 126):
        row = {"h": h}
        for w in ("early", "recent"):
            lo, hi = W[w]
            idxs = np.arange(lo + 252, hi - h, h) if False else np.arange(lo, hi - h, h)
            past = lc[idxs] - lc[idxs - h]
            nxt = lc[idxs + h] - lc[idxs]
            k = len(idxs)
            rho = np.corrcoef(past, nxt)[0, 1]
            row[f"{w}_corr_past_next"] = rho
            row[f"{w}_nonoverlapping_pairs"] = k
            row[f"{w}_t"] = rho * np.sqrt(k - 2) / np.sqrt(1 - rho ** 2)
        rows.append(row)
    return A, pd.DataFrame(rows)


def main():
    pd.set_option("display.width", 250, "display.max_columns", 50, "display.max_rows", 300)
    fm = lambda v: f"{v:,.2f}"
    A, B = part_a()
    print("A1. Daily return autocorrelation")
    print(A.to_string(index=False, float_format=lambda v: f"{v:.3f}"))
    print("\nA2. Correlation of the past h-day return with the next h-day return (non-overlapping blocks)")
    print(B.to_string(index=False, float_format=lambda v: f"{v:.2f}"))
    A.to_csv(OUT / "d4_autocorr.csv", index=False)
    B.to_csv(OUT / "d4_momentum_corr.csv", index=False)

    # ----- trend and momentum states
    cl = S(c)
    rows = []
    mom = lambda k: (cl / cl.shift(k) - 1).values
    states = {
        "close above 50-day avg": (cl > cl.rolling(50).mean()).values,
        "close above 100-day avg": (cl > cl.rolling(100).mean()).values,
        "close above 200-day avg": (cl > cl.rolling(200).mean()).values,
        "21-day return > 0": mom(21) > 0,
        "63-day return > 0": mom(63) > 0,
        "126-day return > 0": mom(126) > 0,
        "252-day return > 0": mom(252) > 0,
        "within 15% of 252-day high": (cl >= 0.85 * cl.rolling(252).max()).values,
        "more than 30% below 252-day high": (cl <= 0.70 * cl.rolling(252).max()).values,
    }
    for k, v in states.items():
        valid = ~np.isnan(S(mom(252)).values) if False else np.ones(n, dtype=bool)
        state_effect(k, np.where(np.isnan(cl.rolling(252).max().values), np.nan, v.astype(float)), (1, 21, 63), rows)
    # ----- volatility regimes
    vol = S(ret).rolling(21).std().values * np.sqrt(252)
    vpct = S(vol).rolling(252).apply(lambda a: (a[:-1] < a[-1]).mean(), raw=True).values
    states_v = {"21-day volatility in top 20% of past year": np.where(np.isnan(vpct), np.nan, (vpct >= 0.8).astype(float)),
                "21-day volatility in bottom 20% of past year": np.where(np.isnan(vpct), np.nan, (vpct <= 0.2).astype(float))}
    for k, v in states_v.items():
        state_effect(k, v, (1, 21, 63), rows)
    # ----- market and sector
    q200 = S(qqq.close.values)
    s200 = S(smh.close.values)
    qab = (q200 > q200.rolling(200).mean()).values.astype(float)
    qab[np.isnan(q200.rolling(200).mean().values)] = np.nan
    sab = (s200 > s200.rolling(200).mean()).values.astype(float)
    sab[np.isnan(s200.rolling(200).mean().values)] = np.nan
    qdd = (q200 <= 0.90 * q200.rolling(252).max()).values.astype(float)
    qdd[np.isnan(q200.rolling(252).max().values)] = np.nan
    rel = (S(lc) - S(lc).shift(63) - (np.log(s200) - np.log(s200).shift(63))).values
    for k, v in {"QQQ above its 200-day avg": qab, "SMH above its 200-day avg": sab, "QQQ 10%+ below its 252-day high": qdd, "AMD 63-day return beats SMH's": np.where(np.isnan(rel), np.nan, (rel > 0).astype(float))}.items():
        state_effect(k, v, (1, 21, 63), rows)
    T = pd.DataFrame(rows)
    T.to_csv(OUT / "d4_state_effects.csv", index=False)
    print("\nB. Signal ON minus OFF: difference in mean forward return (percent, from the next open), with Newey-West t-statistics. Share_on = fraction of days the signal was on.")
    print(T.to_string(index=False, float_format=fm))

    # ----- events: big days
    erows = []
    for name, ev in {"day down 5% or more": ret <= np.log(0.95), "day down 8% or more": ret <= np.log(0.92), "day up 5% or more": ret >= np.log(1.05), "day up 8% or more": ret >= np.log(1.08),
                     "5-day fall of 15% or more": (S(lc) - S(lc).shift(5)).values <= np.log(0.85), "5-day rise of 15% or more": (S(lc) - S(lc).shift(5)).values >= np.log(1.15),
                     "63-day fall of 30% or more": (S(lc) - S(lc).shift(63)).values <= np.log(0.70)}.items():
        event_effect(name, np.nan_to_num(ev, nan=0).astype(bool), (1, 5, 21), 21, erows)
    E = pd.DataFrame(erows)
    E.to_csv(OUT / "d4_event_effects.csv", index=False)
    print("\nC. After big days or runs (events at least 21 days apart): average forward return against the period's ordinary average for the same horizon")
    print(E.to_string(index=False, float_format=fm))

    # ----- reports
    rep = sorted({int(idx.searchsorted(d)) for d in report_dates() if d >= pd.Timestamp("2012-06-01")})
    rrows, prof = [], []
    for w in ("early", "recent"):
        lo, hi = W[w]
        rs = [r for r in rep if lo + 25 <= r and r + 70 < (hi if w == "early" else n)]
        react = np.array([lc[r + 1] - lc[r] for r in rs])
        pre10 = np.array([lc[r] - lc[r - 10] for r in rs])
        pre21 = np.array([lc[r] - lc[r - 21] for r in rs])
        post = {h: np.array([lc[r + 1 + h] - lc[r + 1] for r in rs]) for h in (5, 21, 42)}
        ordinary = {h: np.nanmean(np.where(period_mask(w, h), FWD[h], np.nan)) for h in (5, 21, 42)}
        daily = np.nanmean(ret[lo:hi])
        sd = lambda a: a.std(ddof=1) / np.sqrt(len(a))
        rrows.append({"period": w, "reports": len(rs), "reaction_mean_pct": 100 * (np.exp(react.mean()) - 1), "reaction_median_pct": 100 * (np.exp(np.median(react)) - 1), "reaction_down_share": float((react < 0).mean()),
                      "reaction_abs_mean_pct": 100 * np.abs(react).mean(), "ordinary_day_abs_pct": 100 * np.nanmean(np.abs(ret[lo:hi])), "reaction_vs_ordinary_t": (react.mean() - daily) / sd(react),
                      "pre10_mean_pct": 100 * (np.exp(pre10.mean()) - 1), "pre10_t": (pre10.mean() - 10 * daily) / sd(pre10), "pre21_mean_pct": 100 * (np.exp(pre21.mean()) - 1), "pre21_t": (pre21.mean() - 21 * daily) / sd(pre21),
                      **{f"post{h}_mean_pct": 100 * (np.exp(post[h].mean()) - 1) for h in (5, 21, 42)}, **{f"post{h}_ordinary_pct": 100 * (np.exp(ordinary[h]) - 1) for h in (5, 21, 42)},
                      **{f"post{h}_t": (post[h].mean() - ordinary[h]) / sd(post[h]) for h in (5, 21, 42)},
                      "corr_reaction_next21": float(np.corrcoef(react, post[21])[0, 1]), "corr_reaction_next42": float(np.corrcoef(react, post[42])[0, 1]),
                      "post21_after_down_reaction_pct": 100 * (np.exp(post[21][react < -0.05].mean()) - 1) if (react < -0.05).sum() > 1 else np.nan, "n_down5": int((react < -0.05).sum()),
                      "post21_after_up_reaction_pct": 100 * (np.exp(post[21][react > 0.05].mean()) - 1) if (react > 0.05).sum() > 1 else np.nan, "n_up5": int((react > 0.05).sum())})
    R = pd.DataFrame(rrows).T
    R.to_csv(OUT / "d4_reports.csv")
    print("\nD. Around earnings reports (after-close reports; reaction = next day's close against the report-day close). Post windows start from the reaction-day CLOSE (a rule could act at the next open)")
    print(R.to_string(float_format=lambda v: f"{v:,.2f}", header=True))

    # ----- AMD vs market: day by day
    mrows = []
    for w in ("early", "recent"):
        lo, hi = W[w]
        m = slice(lo + 1, hi - 1)
        # next-day AMD return (close to close) vs today's QQQ / SMH / own return
        nxt = ret[lo + 2:hi]
        for nm, x in (("AMD own", ret), ("QQQ", qret), ("SMH", sret)):
            mrows.append({"period": w, "today": nm, "corr_with_AMD_next_day": float(np.corrcoef(x[lo + 1:hi - 1], nxt)[0, 1])})
        beta = np.polyfit(qret[lo + 1:hi], ret[lo + 1:hi], 1)[0]
        beta_s = np.polyfit(sret[lo + 1:hi], ret[lo + 1:hi], 1)[0]
        mrows.append({"period": w, "today": "beta to QQQ", "corr_with_AMD_next_day": beta})
        mrows.append({"period": w, "today": "beta to SMH", "corr_with_AMD_next_day": beta_s})
        mrows.append({"period": w, "today": "corr of same-day returns, AMD and SMH", "corr_with_AMD_next_day": float(np.corrcoef(sret[lo + 1:hi], ret[lo + 1:hi])[0, 1])})
    M = pd.DataFrame(mrows)
    M.to_csv(OUT / "d4_market.csv", index=False)
    print("\nE. Market and sector links")
    print(M.to_string(index=False, float_format=lambda v: f"{v:.3f}"))

    # ----- volatility clustering
    vrows = []
    fvol = S(ret).rolling(21).std().shift(-21).values * np.sqrt(252)
    for w in ("early", "recent"):
        lo, hi = W[w]
        sl = slice(lo + 22, hi - 22)
        a, b = vol[sl], fvol[sl]
        m = ~(np.isnan(a) | np.isnan(b))
        vrows.append({"period": w, "corr_vol21_now_vs_next21": float(np.corrcoef(a[m], b[m])[0, 1]), "avg_vol": float(np.nanmean(a)), "avg_vol_top20pct_state": float(np.nanmean(a[vpct[sl] >= 0.8])), "next21_vol_in_top20pct_state": float(np.nanmean(b[m & (vpct[sl] >= 0.8)])),
                      "next21_vol_in_bottom20pct_state": float(np.nanmean(b[m & (vpct[sl] <= 0.2)])), "worst_21d_fwd_in_top20": float(np.nanmin(np.where(vpct[sl] >= 0.8, FWD[21][sl], np.nan))), "worst_21d_fwd_in_bottom20": float(np.nanmin(np.where(vpct[sl] <= 0.2, FWD[21][sl], np.nan)))})
    V = pd.DataFrame(vrows)
    V.to_csv(OUT / "d4_vol.csv", index=False)
    print("\nF. Volatility persistence (annualised vol; worst 21-day forward log return in each state)")
    print(V.to_string(index=False, float_format=lambda v: f"{v:.2f}"))

    # ----- Part G: plain in/out rules from these signals, in dollars against held
    g = []
    ma = lambda k: cl.rolling(k).mean().values
    sigs = {
        "in while above 50-day avg": c > ma(50), "in while above 100-day avg": c > ma(100), "in while above 200-day avg": c > ma(200),
        "in while 63-day return > 0": mom(63) > 0, "in while 126-day return > 0": mom(126) > 0, "in while 252-day return > 0": mom(252) > 0,
        "in unless 21-day vol in top 20% of year": ~(vpct >= 0.8), "in unless 63-day return < -15%": ~(mom(63) < -0.15),
        "in while QQQ above 200-day avg": qab == 1, "in while SMH above 200-day avg": sab == 1,
        "in while above 200-day avg AND SMH above its 200": (c > ma(200)) & (sab == 1),
        "in unless more than 30% below 252-day high": ~(c <= 0.70 * cl.rolling(252).max().values),
    }
    for nm, s in sigs.items():
        row = {"rule": nm}
        for w in ("early", "recent"):
            lo, hi = W[w]
            pos = np.where(np.isnan(s.astype(float)), 0.0, s.astype(float))
            pos[:lo - 1] = 0
            m = mult(pos, o, c, lo, hi)
            H = hold_mult(o, c, lo, hi)
            eq = curve(pos, o, c, lo, hi)
            yrs = (hi - lo) / 252
            row.update({f"{w}_x": m, f"{w}_over_held": m / H, f"{w}_maxdd": max_dd(eq), f"{w}_trades_per_year": len(trades_from_pos(pos, lo, hi)) / yrs, f"{w}_in_market": float(pos[lo - 1:hi - 1].mean())})
        g.append(row)
    G = pd.DataFrame(g)
    G.to_csv(OUT / "d4_plain_rules.csv", index=False)
    print("\nG. Plain pre-listed in/out rules (not tuned). Held: recent {:.2f}x, max drawdown {:.0%}; early {:.1f}x, max drawdown {:.0%}".format(
        hold_mult(o, c, *W["recent"]), max_dd(curve(np.ones(n), o, c, *W["recent"])), hold_mult(o, c, *W["early"]), max_dd(curve(np.ones(n), o, c, *W["early"]))))
    print(G.to_string(index=False, float_format=lambda v: f"{v:,.2f}"))


if __name__ == "__main__":
    main()
