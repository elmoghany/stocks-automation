"""TradingView-style indicators rewritten in pandas from the ideas in INDICATOR_PLAN.md, and tested against its steps 1 to 4. No orders.

Written from each indicator's published formula, using daily bars and past data only. Settings are each script's defaults; where a script gives
no explicit signal, the event is my choice. Step 1 recomputes everything on shortened data to catch look-ahead.
Writes results/amd_tv_indicators.csv and results/amd_tv_signals.json for the backtest.
"""
import json

import numpy as np
import pandas as pd

import amd_ta_brainstorm as B

RES, BAR = B.RES, B.BAR


def rma(s, n):
    return s.ewm(alpha=1 / n, adjust=False).mean()


def ema(s, n):
    return s.ewm(span=n, adjust=False).mean()


def rsi(s, n):
    d = s.diff()
    return 100 - 100 / (1 + rma(d.clip(lower=0), n) / rma((-d.clip(upper=0)), n))


def up(a, b):
    return (a > b) & (a.shift() <= (b.shift() if isinstance(b, pd.Series) else b))


def dn(a, b):
    return (a < b) & (a.shift() >= (b.shift() if isinstance(b, pd.Series) else b))


def flips(state):
    return (state == 1) & (state.shift() == -1), (state == -1) & (state.shift() == 1)


def signals(o, h, l, c, v):
    """Buy events, sell events and regime states for the bars given."""
    buy, sell, state = {}, {}, {}
    idx = c.index
    tp = (h + l + c) / 3
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    atr14 = rma(tr, 14)
    cv, hv, lv, ov, vv = c.values, h.values, l.values, o.values, v.values
    n = len(c)

    # KAMA: speed follows the efficiency of the move
    change = (c - c.shift(14)).abs()
    er = (change / c.diff().abs().rolling(14).sum()).fillna(0).values
    k = np.full(n, np.nan)
    k[14] = cv[14]
    for i in range(15, n):
        a = (er[i] * (2 / 3 - 2 / 31) + 2 / 31) ** 2
        k[i] = k[i - 1] + a * (cv[i] - k[i - 1])
    kama = pd.Series(k, index=idx)
    slope = np.sign(kama.diff())
    buy["KAMA turns up"], sell["KAMA turns down"] = (slope > 0) & (slope.shift() < 0), (slope < 0) & (slope.shift() > 0)

    # FRAMA: fractal dimension sets the speed
    n1 = (h.rolling(7).max() - l.rolling(7).min()) / 7
    n2 = n1.shift(7)
    n3 = (h.rolling(14).max() - l.rolling(14).min()) / 14
    dim = (np.log(n1 + n2) - np.log(n3)) / np.log(2)
    alpha = np.exp(-4.6 * (dim - 1)).clip(0.01, 1).fillna(1).values
    f = cv.copy().astype(float)
    for i in range(1, n):
        f[i] = alpha[i] * cv[i] + (1 - alpha[i]) * f[i - 1]
    frama = pd.Series(f, index=idx)
    slope = np.sign(frama.diff())
    buy["FRAMA turns up"], sell["FRAMA turns down"] = (slope > 0) & (slope.shift() < 0), (slope < 0) & (slope.shift() > 0)

    # TRAMA: speed follows how often new highs or lows appear
    hh, ll = h.rolling(99).max(), l.rolling(99).min()
    tc = (((hh > hh.shift()) | (ll < ll.shift())).astype(float).rolling(99).mean() ** 2).fillna(0).values
    t = cv.copy().astype(float)
    for i in range(1, n):
        t[i] = t[i - 1] + tc[i] * (cv[i] - t[i - 1])
    trama = pd.Series(t, index=idx)
    buy["close crosses above TRAMA"], sell["close crosses below TRAMA"] = up(c, trama), dn(c, trama)

    # OTT: VIDYA with a ratcheting 1.4% stop
    d = c.diff()
    s_up, s_dn = d.clip(lower=0).rolling(9).sum(), (-d.clip(upper=0)).rolling(9).sum()
    cmo = ((s_up - s_dn) / (s_up + s_dn)).abs().fillna(0).values
    var = cv.copy().astype(float)
    a0 = 2 / 3
    for i in range(1, n):
        var[i] = a0 * cmo[i] * cv[i] + (1 - a0 * cmo[i]) * var[i - 1]
    long_stop, short_stop = var * 0.986, var * 1.014
    direction = np.ones(n)
    for i in range(1, n):
        long_stop[i] = max(long_stop[i], long_stop[i - 1]) if var[i] > long_stop[i - 1] else long_stop[i]
        short_stop[i] = min(short_stop[i], short_stop[i - 1]) if var[i] < short_stop[i - 1] else short_stop[i]
        direction[i] = 1 if direction[i - 1] == -1 and var[i] > short_stop[i - 1] else -1 if direction[i - 1] == 1 and var[i] < long_stop[i - 1] else direction[i - 1]
    buy["OTT flips up"], sell["OTT flips down"] = flips(pd.Series(direction, index=idx))

    # AlphaTrend: money flow decides which ATR stop ratchets
    flow = tp * v
    pos = flow.where(tp > tp.shift(), 0).rolling(14).sum()
    neg = flow.where(tp < tp.shift(), 0).rolling(14).sum()
    mfi = (100 - 100 / (1 + pos / neg)).fillna(50).values
    at = np.zeros(n)
    av = atr14.values
    for i in range(1, n):
        lo, hi = lv[i] - av[i], hv[i] + av[i]
        at[i] = max(lo, at[i - 1]) if mfi[i] >= 50 else (min(hi, at[i - 1]) if at[i - 1] > 0 else hi)
    alpha_t = pd.Series(at, index=idx)
    buy["AlphaTrend crosses up"], sell["AlphaTrend crosses down"] = up(alpha_t, alpha_t.shift(2)), dn(alpha_t, alpha_t.shift(2))

    # SSL channel
    hi10, lo10 = h.rolling(10).mean().values, l.rolling(10).mean().values
    st = np.zeros(n)
    for i in range(1, n):
        st[i] = 1 if cv[i] > hi10[i] else -1 if cv[i] < lo10[i] else st[i - 1]
    buy["SSL flips up"], sell["SSL flips down"] = flips(pd.Series(st, index=idx))

    # QQE: smoothed RSI against a trailing band
    r = ema(rsi(c, 8), 3)
    band_size = ema(ema(r.diff().abs(), 15), 15) * 3
    rv, bs = r.values, band_size.values
    trail = np.nan_to_num(rv.copy())
    for i in range(1, n):
        if not np.isfinite(rv[i]) or not np.isfinite(bs[i]):
            continue
        if rv[i] > trail[i - 1]:
            trail[i] = max(trail[i - 1], rv[i] - bs[i]) if rv[i - 1] > trail[i - 1] else rv[i] - bs[i]
        else:
            trail[i] = min(trail[i - 1], rv[i] + bs[i]) if rv[i - 1] < trail[i - 1] else rv[i] + bs[i]
    tq = pd.Series(trail, index=idx)
    buy["QQE crosses up"], sell["QQE crosses down"] = up(r, tq), dn(r, tq)

    # WaveTrend
    esa = ema(tp, 10)
    dev = ema((tp - esa).abs(), 10)
    wt1 = ema((tp - esa) / (0.015 * dev), 21)
    wt2 = wt1.rolling(4).mean()
    buy["WaveTrend crosses up"], sell["WaveTrend crosses down"] = up(wt1, wt2), dn(wt1, wt2)
    buy["WaveTrend crosses up below -53"] = up(wt1, wt2) & (wt1 < -53)
    sell["WaveTrend crosses down above 53"] = dn(wt1, wt2) & (wt1 > 53)

    # Stochastic Connors RSI
    streak = np.zeros(n)
    for i in range(1, n):
        streak[i] = (streak[i - 1] + 1 if streak[i - 1] > 0 else 1) if cv[i] > cv[i - 1] else (streak[i - 1] - 1 if streak[i - 1] < 0 else -1) if cv[i] < cv[i - 1] else 0
    crsi = (rsi(c, 3) + rsi(pd.Series(streak, index=idx), 2) + c.pct_change(fill_method=None).rolling(100).rank(pct=True) * 100) / 3
    sc = (100 * (crsi - crsi.rolling(3).min()) / (crsi.rolling(3).max() - crsi.rolling(3).min())).rolling(3).mean()
    buy["Stochastic Connors RSI back above 20"], sell["Stochastic Connors RSI back below 80"] = up(sc, 20), dn(sc, 80)
    buy["Connors RSI below 15"], sell["Connors RSI above 85"] = crsi < 15, crsi > 85

    # Laguerre RSI
    g = 0.7
    l0, l1, l2, l3 = np.zeros(n), np.zeros(n), np.zeros(n), np.zeros(n)
    lrsi = np.full(n, 0.5)
    for i in range(1, n):
        l0[i] = (1 - g) * cv[i] + g * l0[i - 1]
        l1[i] = -g * l0[i] + l0[i - 1] + g * l1[i - 1]
        l2[i] = -g * l1[i] + l1[i - 1] + g * l2[i - 1]
        l3[i] = -g * l2[i] + l2[i - 1] + g * l3[i - 1]
        cu = max(l0[i] - l1[i], 0) + max(l1[i] - l2[i], 0) + max(l2[i] - l3[i], 0)
        cd = max(l1[i] - l0[i], 0) + max(l2[i] - l1[i], 0) + max(l3[i] - l2[i], 0)
        lrsi[i] = cu / (cu + cd) if cu + cd else lrsi[i - 1]
    lag = pd.Series(lrsi, index=idx)
    buy["Laguerre RSI back above .2"], sell["Laguerre RSI back below .8"] = up(lag, 0.2), dn(lag, 0.8)

    # CTI, Trendscore, Phase Change Index
    line = pd.Series(np.arange(n, dtype=float), index=idx)
    cti = c.rolling(12).corr(line)
    buy["CTI crosses above 0"], sell["CTI crosses below 0"] = up(cti, 0), dn(cti, 0)
    buy["CTI below -.8"], sell["CTI above .8"] = cti < -0.8, cti > 0.8
    score = sum(np.sign(c - c.shift(i)) for i in range(11, 21))
    buy["Trendscore crosses above 0"], sell["Trendscore crosses below 0"] = up(score, 0), dn(score, 0)
    pci = np.full(n, np.nan)
    for i in range(35, n):
        w = cv[i - 35:i + 1]
        straight = w[0] + (w[-1] - w[0]) * np.arange(36) / 35
        gap = w[1:-1] - straight[1:-1]
        total = np.abs(gap).sum()
        pci[i] = 100 * gap[gap > 0].sum() / total if total else 50
    pci = pd.Series(pci, index=idx)
    buy["Phase Change Index back above 20"], sell["Phase Change Index back below 80"] = up(pci, 20), dn(pci, 80)

    # Squeeze Momentum
    mid, sd = c.rolling(20).mean(), c.rolling(20).std()
    kc = tr.rolling(20).mean()
    squeeze = ((mid + 2 * sd) < (mid + 1.5 * kc)) & ((mid - 2 * sd) > (mid - 1.5 * kc))
    center = c - ((h.rolling(20).max() + l.rolling(20).min()) / 2 + mid) / 2
    mom = center.rolling(20).apply(lambda w: np.polyval(np.polyfit(np.arange(20.0), w, 1), 19), raw=True)
    release = (~squeeze) & squeeze.shift().fillna(False)
    buy["squeeze release, momentum up"], sell["squeeze release, momentum down"] = release & (mom > 0), release & (mom < 0)
    buy["squeeze momentum turns up below 0"] = (mom > mom.shift()) & (mom.shift() <= mom.shift(2)) & (mom < 0)
    sell["squeeze momentum turns down above 0"] = (mom < mom.shift()) & (mom.shift() >= mom.shift(2)) & (mom > 0)

    # Williams VIX Fix: AMD's own fear gauge
    wvf = (c.rolling(22).max() - l) / c.rolling(22).max() * 100
    alert = (wvf >= wvf.rolling(20).mean() + 2 * wvf.rolling(20).std()) | (wvf >= wvf.rolling(50).max() * 0.85)
    buy["Williams VIX Fix alert"] = alert & ~alert.shift().fillna(False)
    buy["Williams VIX Fix alert ends"] = (~alert) & alert.shift().fillna(False)
    wvf_up = (c - c.rolling(22).min()) / c.rolling(22).min() * 100  # the same idea, upside down, is my own extension
    high_alert = (wvf_up >= wvf_up.rolling(20).mean() + 2 * wvf_up.rolling(20).std()) | (wvf_up >= wvf_up.rolling(50).max() * 0.85)
    sell["inverted VIX Fix alert ends"] = (~high_alert) & high_alert.shift().fillna(False)

    # Waddah Attar
    macd_fast = ema(c, 20) - ema(c, 40)
    t1 = 150 * macd_fast.diff()
    width = 4 * sd
    dead = 3.7 * rma(tr, 100)
    buy["Waddah Attar up surge"] = up(t1, pd.concat([width, dead], axis=1).max(axis=1))
    sell["Waddah Attar turns negative"] = dn(t1, 0)

    # Volatility Ratio
    tr_range = pd.concat([h.rolling(14).max(), c.shift(15)], axis=1).max(axis=1) - pd.concat([l.rolling(14).min(), c.shift(15)], axis=1).min(axis=1)
    ratio = tr / tr_range
    buy["Volatility Ratio .5, up close"], sell["Volatility Ratio .5, down close"] = (ratio >= 0.5) & (c > c.shift()), (ratio >= 0.5) & (c < c.shift())

    # VFI, VPCI, NVI
    inter = np.log(tp) - np.log(tp.shift())
    cutoff = 0.2 * inter.rolling(30).std() * c
    avg_vol = v.rolling(130).mean().shift()
    capped = pd.concat([v, avg_vol * 2.5], axis=1).min(axis=1)
    mf = tp - tp.shift()
    signed = capped.where(mf > cutoff, -capped.where(mf < -cutoff, 0))
    vfi = ema(signed.rolling(130).sum() / avg_vol, 3)
    buy["VFI crosses above 0"], sell["VFI crosses below 0"] = up(vfi, 0), dn(vfi, 0)
    vwma = lambda k: (c * v).rolling(k).sum() / v.rolling(k).sum()
    vpci = (vwma(20) - c.rolling(20).mean()) * (vwma(5) / c.rolling(5).mean()) * (v.rolling(5).mean() / v.rolling(20).mean())
    buy["VPCI crosses above 0"], sell["VPCI crosses below 0"] = up(vpci, 0), dn(vpci, 0)
    nvi = np.ones(n) * 1000.0
    for i in range(1, n):
        nvi[i] = nvi[i - 1] * (cv[i] / cv[i - 1]) if vv[i] < vv[i - 1] else nvi[i - 1]
    nvi = pd.Series(nvi, index=idx)
    buy["NVI crosses above its 255d EMA"], sell["NVI crosses below its 255d EMA"] = up(nvi, ema(nvi, 255)), dn(nvi, ema(nvi, 255))

    # Weis Wave: volume per swing
    trend = np.zeros(n)
    wave = np.zeros(n)
    last_up, last_down = 0.0, 0.0
    wave_buy, wave_sell = np.zeros(n, dtype=bool), np.zeros(n, dtype=bool)
    for i in range(2, n):
        m0, m1 = np.sign(cv[i] - cv[i - 1]), np.sign(cv[i - 1] - cv[i - 2])
        trend[i] = m0 if m0 != 0 and m0 == m1 else trend[i - 1]
        if trend[i] == trend[i - 1]:
            wave[i] = wave[i - 1] + vv[i]
        else:
            if trend[i - 1] > 0:
                last_up = wave[i - 1]
            elif trend[i - 1] < 0:
                last_down = wave[i - 1]
            wave[i] = vv[i]
        wave_buy[i] = trend[i] > 0 and wave[i] > last_down > 0 and wave[i - 1] <= last_down
        wave_sell[i] = trend[i] < 0 and wave[i] > last_up > 0 and wave[i - 1] <= last_up
    buy["Weis Wave, up wave beats last down wave"] = pd.Series(wave_buy, index=idx)
    sell["Weis Wave, down wave beats last up wave"] = pd.Series(wave_sell, index=idx)

    # Pocket Pivot
    down_vol = v.where(c < c.shift(), 0).rolling(10).max().shift()
    buy["Pocket Pivot"] = (c >= o * 1.03) & (v >= down_vol)
    sell["reverse Pocket Pivot"] = (c <= o * 0.97) & (v >= v.where(c > c.shift(), 0).rolling(10).max().shift())  # the mirror is my own extension

    # Leledc, TD Setup
    ups = (c > c.shift(4)).astype(int)
    downs = (c < c.shift(4)).astype(int)
    up_count = ups.groupby((ups == 0).cumsum()).cumsum()
    down_count = downs.groupby((downs == 0).cumsum()).cumsum()
    sell["Leledc exhaustion"] = (up_count.shift() > 6) & (c < o) & (h >= h.rolling(12).max())
    buy["Leledc exhaustion"] = (down_count.shift() > 6) & (c > o) & (l <= l.rolling(12).min())
    buy["TD Setup 9 down"], sell["TD Setup 9 up"] = down_count == 9, up_count == 9

    # Liquidity sweep, failure swing
    body = (c - o).abs()
    lower, upper = pd.concat([o, c], axis=1).min(axis=1) - l, h - pd.concat([o, c], axis=1).max(axis=1)
    buy["liquidity sweep of the 15d low"] = (l < l.rolling(15).min().shift()) & (c > l.rolling(15).min().shift()) & (c > o) & (lower > 1.5 * body)
    sell["liquidity sweep of the 15d high"] = (h > h.rolling(15).max().shift()) & (c < h.rolling(15).max().shift()) & (c < o) & (upper > 1.5 * body)
    for k in (42, 84):
        buy[f"failure swing at the {k}d low"] = (l <= l.rolling(k).min().shift()) & (c > l.rolling(k).min().shift())
        sell[f"failure swing at the {k}d high"] = (h >= h.rolling(k).max().shift()) & (c < h.rolling(k).max().shift())

    # Fair value gap, first touch within 20 bars. I read the detection, not the script's full touch logic.
    fvg_buy, fvg_sell = np.zeros(n, dtype=bool), np.zeros(n, dtype=bool)
    for i in range(2, n):
        if lv[i] > hv[i - 2] * 1.005:
            for j in range(i + 1, min(i + 21, n)):
                if lv[j] <= hv[i - 2]:
                    fvg_buy[j] = True
                    break
        if hv[i] < lv[i - 2] * 0.995:
            for j in range(i + 1, min(i + 21, n)):
                if hv[j] >= lv[i - 2]:
                    fvg_sell[j] = True
                    break
    buy["fair value gap first touch"], sell["fair value gap first touch"] = pd.Series(fvg_buy, index=idx), pd.Series(fvg_sell, index=idx)

    # Market structure: pivots count only once confirmed, 14 bars later
    last_high, last_low = np.nan, np.nan
    ms = np.zeros(n)
    for i in range(29, n):
        p = i - 14
        if hv[p] == hv[p - 14:i + 1].max():
            last_high = hv[p]
        if lv[p] == lv[p - 14:i + 1].min():
            last_low = lv[p]
        ms[i] = 1 if np.isfinite(last_high) and cv[i] > last_high else -1 if np.isfinite(last_low) and cv[i] < last_low else ms[i - 1]
    buy["market structure flips up"], sell["market structure flips down"] = flips(pd.Series(ms, index=idx))

    # Regime filters
    rets = np.log(c).diff().values
    hurst = np.full(n, np.nan)
    for i in range(100, n):
        w = rets[i - 99:i + 1]
        points = []
        for size in (6, 12, 25, 50, 100):
            parts = [w[j:j + size] for j in range(0, 100 - size + 1, size)]
            ratios = []
            for part in parts:
                dev_ = np.cumsum(part - part.mean())
                s = part.std()
                if s > 0:
                    ratios.append((dev_.max() - dev_.min()) / s)
            points.append((np.log(size), np.log(np.mean(ratios))))
        xs, ys = zip(*points)
        hurst[i] = np.polyfit(xs, ys, 1)[0]
    hurst = pd.Series(hurst, index=idx)
    state["Hurst above .55"], state["Hurst below .5"] = hurst > 0.55, hurst < 0.5
    chop = 100 * np.log10(tr.rolling(14).sum() / (h.rolling(14).max() - l.rolling(14).min())) / np.log10(14)
    state["Choppiness below 38"], state["Choppiness above 62"] = chop < 38.2, chop > 61.8
    stiff = ema(100 * ((c > c.rolling(100).mean() - 0.2 * c.rolling(100).std()).astype(float).rolling(60).mean()), 3)
    state["Stiffness above 90"], state["Stiffness below 50"] = stiff > 90, stiff < 50
    state["above 50d avg"], state["below 50d avg"] = c > c.rolling(50).mean(), c < c.rolling(50).mean()
    state["above 200d avg"], state["below 200d avg"] = c > c.rolling(200).mean(), c < c.rolling(200).mean()
    return buy, sell, state


def main():
    full_buy, full_sell, full_state = signals(B.o, B.h, B.l, B.c, B.v)
    context = {"SMH within 5% of its 1y high": B.smh >= B.smh.rolling(252).max() * 0.95, "QQQ below 100d avg": B.qqq < B.qqq.rolling(100).mean(),
               "QQQ above 100d avg": B.qqq > B.qqq.rolling(100).mean(), "VIX above 25": B.vix > 25}
    bad = set()
    for cut in ("2024-06-28", "2025-06-30", "2026-03-31"):
        part = lambda s: s.loc[:cut]
        pb, ps, pst = signals(part(B.o), part(B.h), part(B.l), part(B.c), part(B.v))
        for name, mine, full in (("buy", pb, full_buy), ("sell", ps, full_sell), ("state", pst, full_state)):
            for k in mine:
                if not mine[k].equals(full[k].loc[:cut]):
                    bad.add((name, k))
    print(f"signals: buy {len(full_buy)}, sell {len(full_sell)}, filters {len(full_state) + len(context)}; change when later data arrives: {sorted(bad)}", flush=True)
    for name, k in bad:
        (full_buy if name == "buy" else full_sell if name == "sell" else full_state).pop(k, None)
    filters = {f"[{k}]": f for k, f in {**full_state, **context}.items()}
    tables = {"buy": {**full_buy, **filters}, "sell": {**full_sell, **filters}}
    idx, masks, starts = B.idx, B.masks, B.starts_of
    arrays = {side: {k: f.reindex(idx).fillna(False).values.astype(bool) for k, f in t.items()} for side, t in tables.items()}

    def run(side, shift=0):
        wide, tight = np.roll(B.outcomes[side]["wide"], shift), np.roll(B.outcomes[side]["tight"], shift)
        names = [k for k in arrays[side] if not k.startswith("[")]
        combos = [(k,) for k in names] + [(k, f) for k in names for f in filters]
        rows = []
        for combo in combos:
            flag = arrays[side][combo[0]] if len(combo) == 1 else arrays[side][combo[0]] & arrays[side][combo[1]]
            s = starts(flag & masks["main"])
            if len(s) < B.MIN_N:
                continue
            c_s = starts(flag & masks["check"])
            w, t, cw, ct = wide[s], tight[s], wide[c_s], tight[c_s]
            w, t, cw, ct = w[np.isfinite(w)], t[np.isfinite(t)], cw[np.isfinite(cw)], ct[np.isfinite(ct)]
            rows.append({"side": side, "signal": " + ".join(combo), "size": len(combo), "n": len(s), "wide": w.mean() if len(w) else np.nan, "wide_n": len(w), "tight": t.mean() if len(t) else np.nan, "tight_n": len(t),
                         "n_2024": len(c_s), "wide_2024": cw.mean() if len(cw) else np.nan, "wide_n_2024": len(cw), "tight_2024": ct.mean() if len(ct) else np.nan, "tight_n_2024": len(ct)})
        return pd.DataFrame(rows)

    def counts(t):
        if t.empty:
            return 0, 0, 0
        one = ((t.wide >= BAR) & (t.wide_n >= 4)) | ((t.tight >= BAR) & (t.tight_n >= 4))
        w = (t.wide >= BAR) & (t.wide_n >= 4) & (t.wide_2024 >= BAR) & (t.wide_n_2024 >= 3)
        ti = (t.tight >= BAR) & (t.tight_n >= 4) & (t.tight_2024 >= BAR) & (t.tight_n_2024 >= 3)
        return int(one.sum()), int(w.sum()), int(ti.sum())

    rng = np.random.default_rng(9)
    shifts = [int(rng.integers(40, B.n_all - 40)) for _ in range(40)]
    results = []
    pd.set_option("display.width", 220, "display.max_columns", 20, "display.max_rows", 60, "display.max_colwidth", 62)
    fmt = lambda x: f"{x:.2f}"
    show = ["signal", "n", "wide", "wide_n", "tight", "tight_n", "n_2024", "wide_2024", "wide_n_2024", "tight_2024", "tight_n_2024"]
    keep = {}
    for side in ("buy", "sell"):
        t = run(side)
        results.append(t)
        real = counts(t)
        fake = [counts(run(side, s)) for s in shifts]
        print(f"\n=== {side}: tested {len(t)} with at least {B.MIN_N} signals. Pass 2025-26 {real[0]}; also 2024 wide {real[1]}, tight {real[2]}", flush=True)
        for j, label in enumerate(("2025-26", "also 2024 wide", "also 2024 tight")):
            values = sorted(f[j] for f in fake)
            print(f"  rotated {label}: median {int(np.median(values))}, 80th percentile {int(np.percentile(values, 80))}; real beats {sum(real[j] > v for v in values)} of {len(values)}", flush=True)
        singles = t[t["size"] == 1]
        print("single signals, best by wide")
        print(singles.sort_values(["wide", "n"], ascending=False).head(12)[show].to_string(index=False, float_format=fmt))
        print("single signals, best by tight")
        print(singles.sort_values(["tight", "n"], ascending=False).head(8)[show].to_string(index=False, float_format=fmt))
        both = t[((t.wide >= BAR) & (t.wide_n >= 4) & (t.wide_2024 >= BAR) & (t.wide_n_2024 >= 3)) | ((t.tight >= BAR) & (t.tight_n >= 4) & (t.tight_2024 >= BAR) & (t.tight_n_2024 >= 3))]
        print(f"pass in both periods: {len(both)}")
        print(both.sort_values(["n", "n_2024"], ascending=False).head(25)[show].to_string(index=False, float_format=fmt))
        keep[side] = both.sort_values(["n", "n_2024"], ascending=False).head(25).signal.tolist()
    pd.concat(results).to_csv(RES / "amd_tv_indicators.csv", index=False)
    dates = {}
    for side, names in keep.items():
        for name in names:
            parts = name.split(" + ")
            flag = arrays[side][parts[0]] if len(parts) == 1 else arrays[side][parts[0]] & arrays[side][parts[1]]
            dates[f"{side}: {name}"] = [str(d.date()) for d in idx[flag]]
    (RES / "amd_tv_signals.json").write_text(json.dumps(dates), encoding="utf-8")
    print("\nsaved", len(dates), "signals for the backtest")


if __name__ == "__main__":
    main()
