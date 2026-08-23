"""Bar-only liquidity estimators -- the L2-free liquidity layer (W-campaign).

WHY THIS EXISTS. The live paper sessions veto entries on the REAL inside
spread (0.5% cap) read from the platform book. Historical L2 does not
exist and will not be bought, so backtests stand in for the book with
bar statistics. The incumbent stand-in is `spread_proxy` in
plan/rotation_sim.py (median (H-L)/C over the 10 bars before entry).
This module adds the established microstructure estimators so the
calibration study (plan/calibrate_liquidity.py) can test whether any of
them tracks the REAL books logged in data/paper_days better than the
incumbent -- and by how much.

CAUSALITY CONTRACT (the plan/causal.py discipline, replicated):
every estimator is computed from bars STRICTLY BEFORE the decision
timestamp `ts`. The window never touches the entry bar -- the entry
bar's range is a consequence of our own trigger. Each estimator asserts
this on every call, the same loud guard as rotation_sim.spread_proxy.
rotation_sim.py itself is NOT imported and NOT edited (identity runs in
flight); the pattern is replicated, byte-compatible for bar_range_proxy.

Estimators (spread-like ones return PERCENT, comparable to the live
0.5% cap; None = insufficient data, which live treats as NOT vetoed):

  bar_range_proxy   incumbent baseline: median (H-L)/C * 100, 10 bars
  corwin_schultz    Corwin & Schultz (2012) two-bar high-low spread
  abdi_ranaldo      Abdi & Ranaldo (2017) close-high-low spread
  roll              Roll (1984) serial-covariance spread
  amihud            Amihud (2002) |ret|/dollar-volume * 1e6 (DEPTH side;
                    bigger = thinner, not a percent)
  no_trade_share    fraction of calendar minutes with no prints (tape
                    sparseness; relates to the Day-12 stale-pressure
                    finding) -- 0..1, not a percent

Self-test: `python plan/liquidity_estimators.py` simulates a random
walk with a KNOWN 1.0% spread (bid-ask bounce), checks Roll/CS/AR
recover it within documented tolerance, and mechanically proves
causality by mutating every bar at/after ts and asserting the estimates
do not move.
"""

import math

# Estimators are floored at 0 where the paper prescribes it; NEG_FLOOR
# documents that choice in one place.
SQ2 = math.sqrt(2.0)
CS_K = 3.0 - 2.0 * SQ2          # denominator constant in CS alpha

# minimum usable observations per estimator (below -> None)
MIN_PAIRS = 5                    # CS / AR adjacent-bar pairs
MIN_RETS = 8                     # Roll return series length
MIN_AMIHUD = 5                   # bars with positive dollar volume


def _tail_before(df, ts, n):
    """Last `n` bars strictly before `ts`, or None if short.

    Same semantics as rotation_sim.spread_proxy's window and
    causal.CausalView.window: the boundary bar is EXCLUDED, and the
    guard is asserted on every call so an off-by-one cannot silently
    manufacture a future signal.
    """
    w = df[df.index < ts]
    if len(w) < n:
        return None
    tail = w.iloc[-n:]
    # LEAK GATE (loud, every call -- rotation_sim.spread_proxy pattern)
    assert tail.index.max() < ts, (
        f"FUTURE LEAK in liquidity estimator: window max "
        f"{tail.index.max()} >= decision ts {ts}")
    return tail


def bar_range_proxy(df, ts, lookback=10):
    """INCUMBENT baseline: median (H-L)/C over `lookback` bars before ts.

    Byte-for-byte the statistic of rotation_sim.spread_proxy (which is
    not imported -- identity runs in flight). Returns percent, or None.
    LOUD LIMITATION (inherited): bar range conflates volatility with
    book width. That conflation is exactly what the calibration study
    measures.
    """
    tail = _tail_before(df, ts, lookback)
    if tail is None:
        return None
    c = tail["Close"].values
    rng = (tail["High"].values - tail["Low"].values)
    vals = [(r / p) * 100 for r, p in zip(rng, c) if p > 0]
    if not vals:
        return None
    vals.sort()
    n = len(vals)
    return vals[n // 2] if n % 2 else (vals[n // 2 - 1] + vals[n // 2]) / 2


def corwin_schultz(df, ts, lookback=30):
    """Corwin-Schultz (2012) high-low spread over bar pairs. Percent.

    Two-bar beta/gamma with both of the paper's corrections:
    (1) the overnight-gap adjustment, applied here to the between-bar
        gap -- if bar t+1 opens entirely above bar t's high (or below
        its low), bar t+1's H/L are shifted back by the gap before the
        two-bar range is formed;
    (2) negative two-bar spread estimates are set to ZERO, not dropped
        (dropping them biases the mean up; the paper's Section II.C
        correction).
    The per-pair spreads are averaged over the window.
    """
    tail = _tail_before(df, ts, lookback)
    if tail is None:
        return None
    H = tail["High"].values.astype(float)
    L = tail["Low"].values.astype(float)
    O = tail["Open"].values.astype(float)
    spreads = []
    for i in range(len(tail) - 1):
        h1, l1 = H[i], L[i]
        h2, l2 = H[i + 1], L[i + 1]
        o2 = O[i + 1]
        if min(h1, l1, h2, l2, o2) <= 0 or h1 < l1 or h2 < l2:
            continue
        # correction (1): gap adjustment between consecutive bars
        if o2 > h1:
            adj = o2 - h1
            h2, l2 = h2 - adj, l2 - adj
        elif o2 < l1:
            adj = l1 - o2
            h2, l2 = h2 + adj, l2 + adj
        if min(h2, l2) <= 0:
            continue
        b = math.log(h1 / l1) ** 2 + math.log(h2 / l2) ** 2
        g = math.log(max(h1, h2) / min(l1, l2)) ** 2
        alpha = ((math.sqrt(2.0 * b) - math.sqrt(b)) / CS_K
                 - math.sqrt(g / CS_K))
        s = 2.0 * (math.exp(alpha) - 1.0) / (1.0 + math.exp(alpha))
        spreads.append(max(s, 0.0))            # correction (2)
    if len(spreads) < MIN_PAIRS:
        return None
    return 100.0 * sum(spreads) / len(spreads)


def abdi_ranaldo(df, ts, lookback=30):
    """Abdi-Ranaldo (2017) close-high-low spread. Percent.

    s^2 = 4 * E[(c_t - eta_t)(c_t - eta_{t+1})], eta = midpoint of the
    log high-low range. Negative expectation floored at zero (the
    paper's correction for estimates that would be imaginary).
    """
    tail = _tail_before(df, ts, lookback)
    if tail is None:
        return None
    H = tail["High"].values.astype(float)
    L = tail["Low"].values.astype(float)
    C = tail["Close"].values.astype(float)
    xs = []
    for i in range(len(tail) - 1):
        if min(H[i], L[i], C[i], H[i + 1], L[i + 1]) <= 0:
            continue
        c = math.log(C[i])
        eta1 = 0.5 * (math.log(H[i]) + math.log(L[i]))
        eta2 = 0.5 * (math.log(H[i + 1]) + math.log(L[i + 1]))
        xs.append((c - eta1) * (c - eta2))
    if len(xs) < MIN_PAIRS:
        return None
    s2 = 4.0 * sum(xs) / len(xs)
    return 100.0 * math.sqrt(max(s2, 0.0))


def roll(df, ts, lookback=30):
    """Roll (1984) serial-covariance spread on close-to-close log
    returns. Percent.

    s = 2 * sqrt(-cov(r_t, r_{t-1})) when the autocovariance is
    negative; 0.0 when it is non-negative (the standard Harris/Roll
    convention -- trending tapes routinely produce positive autocov,
    and returning None there would gut the premarket sample; a zero is
    an honest 'no bounce detected').
    """
    tail = _tail_before(df, ts, lookback)
    if tail is None:
        return None
    C = tail["Close"].values.astype(float)
    if (C <= 0).any():
        return None
    r = [math.log(C[i + 1] / C[i]) for i in range(len(C) - 1)]
    if len(r) < MIN_RETS:
        return None
    n = len(r) - 1
    m1 = sum(r[1:]) / n
    m0 = sum(r[:-1]) / n
    cov = sum((r[i + 1] - m1) * (r[i] - m0) for i in range(n)) / n
    if cov >= 0:
        return 0.0
    return 100.0 * 2.0 * math.sqrt(-cov)


def amihud(df, ts, lookback=30):
    """Amihud (2002) illiquidity: mean |log ret| / dollar volume, x1e6.

    The DEPTH-side proxy: how many percent the tape moves per million
    dollars traded. NOT a percent spread -- do not compare to the 0.5%
    cap directly; the calibration maps it against logged book depth.
    """
    tail = _tail_before(df, ts, lookback)
    if tail is None:
        return None
    C = tail["Close"].values.astype(float)
    V = tail["Volume"].values.astype(float)
    vals = []
    for i in range(len(tail) - 1):
        dv = C[i + 1] * V[i + 1]
        if dv <= 0 or C[i] <= 0 or C[i + 1] <= 0:
            continue
        vals.append(abs(math.log(C[i + 1] / C[i])) / dv)
    if len(vals) < MIN_AMIHUD:
        return None
    return 1e6 * sum(vals) / len(vals)


def no_trade_share(df, ts, window_min=30, session_open_hour=4):
    """Fraction of the last `window_min` calendar minutes with NO
    prints (0..1). Tape sparseness -- the Day-12 stale-pressure
    finding's quantity.

    Bar files omit (or zero-fill) minutes without trades, so absence of
    a bar in the window counts as a no-trade minute. The window is
    truncated at the session's 04:00 ET start (bars cannot exist before
    it); if fewer than 5 minutes of window remain, returns None.
    """
    import pandas as pd
    w = df[df.index < ts]
    if len(w) == 0:
        return None
    day_open = ts.replace(hour=session_open_hour, minute=0, second=0,
                          microsecond=0)
    start = max(ts - pd.Timedelta(minutes=window_min), day_open)
    total = int((ts - start).total_seconds() // 60)
    if total < 5:
        return None
    win = w[w.index >= start]
    traded_minutes = len({t.replace(second=0, microsecond=0)
                          for t, v in zip(win.index, win["Volume"].values)
                          if v > 0})
    assert len(win) == 0 or win.index.max() < ts, (
        f"FUTURE LEAK in no_trade_share: {win.index.max()} >= {ts}")
    return max(0.0, 1.0 - traded_minutes / total)


SPREAD_ESTIMATORS = {
    "bar_range": bar_range_proxy,
    "corwin_schultz": corwin_schultz,
    "abdi_ranaldo": abdi_ranaldo,
    "roll": roll,
}
OTHER_ESTIMATORS = {
    "amihud": amihud,
    "no_trade_share": no_trade_share,
}


def estimate_all(df, ts, lookback=30, range_lookback=10):
    """Every estimator at one decision timestamp. Dict name -> value
    (None where data is insufficient). Combinations the calibration
    tests (max of CS and bar-range, etc.) are formed downstream."""
    out = {}
    out["bar_range"] = bar_range_proxy(df, ts, range_lookback)
    out["corwin_schultz"] = corwin_schultz(df, ts, lookback)
    out["abdi_ranaldo"] = abdi_ranaldo(df, ts, lookback)
    out["roll"] = roll(df, ts, lookback)
    out["amihud"] = amihud(df, ts, lookback)
    out["no_trade_share"] = no_trade_share(df, ts)
    return out


# --------------------------------------------------------------------
# self-test
# --------------------------------------------------------------------

def _synthetic_bars(n_bars=780, trades_per_bar=8, spread_rel=0.010,
                    sigma_trade=0.0002, p0=20.0, seed=7):
    """Random-walk mid + bid-ask bounce, aggregated to 1-min bars.

    Trades print at mid +/- spread/2 with i.i.d. signs -- the exact
    world Roll (1984) assumes; with several trades per bar the bar high
    sits at the ask and the low at the bid, which is the CS/AR world.
    """
    import random
    import pandas as pd
    rng = random.Random(seed)
    idx = pd.date_range("2026-08-13 04:00", periods=n_bars, freq="1min",
                        tz="America/New_York")
    mid = p0
    rows = []
    for _ in range(n_bars):
        prices = []
        for _ in range(trades_per_bar):
            mid *= math.exp(rng.gauss(0.0, sigma_trade))
            side = 1 if rng.random() < 0.5 else -1
            prices.append(mid * (1 + side * spread_rel / 2))
        rows.append({"Open": prices[0], "High": max(prices),
                     "Low": min(prices), "Close": prices[-1],
                     "Volume": 100.0 * trades_per_bar})
    return pd.DataFrame(rows, index=idx)


def self_test():
    import pandas as pd
    ok = 0

    # 1) KNOWN-SPREAD RECOVERY. True relative spread 1.0%.
    #    Tolerance: [0.5x, 1.6x] of truth. Rationale: with sigma_trade
    #    = 2bp and 8 trades/bar the bounce dominates bar ranges, but
    #    (a) CS's two-bar ranges still carry variance -> upward drift,
    #    (b) sampling error over ~750 pairs is a few tenths of a
    #    percent. These estimators are used for RANKING and threshold
    #    calibration, not as unbiased spread meters -- a factor-of-two
    #    band proves they lock onto the right quantity.
    true_s = 1.0  # percent
    df = _synthetic_bars(spread_rel=true_s / 100)
    ts = df.index[-1] + pd.Timedelta(minutes=1)
    for name, fn in (("roll", roll), ("corwin_schultz", corwin_schultz),
                     ("abdi_ranaldo", abdi_ranaldo)):
        est = fn(df, ts, lookback=len(df))
        assert est is not None and 0.5 * true_s <= est <= 1.6 * true_s, (
            f"{name} failed known-spread recovery: {est} vs {true_s}")
        print(f"  {name:15s} recovered {est:.3f}% (true {true_s:.1f}%)")
        ok += 1

    # zero-spread control: estimators should read ~0, far below true_s
    df0 = _synthetic_bars(spread_rel=0.0, seed=11)
    for name, fn in (("roll", roll), ("abdi_ranaldo", abdi_ranaldo)):
        est0 = fn(df0, ts, lookback=len(df0))
        assert est0 is not None and est0 < 0.25 * true_s, (
            f"{name} zero-spread control failed: {est0}")
        ok += 1

    # 2) CAUSALITY, PROVED MECHANICALLY. Corrupt every bar at/after ts;
    #    no estimate may move. (The assert inside _tail_before is the
    #    guard; this proves the slicing too.)
    mid = df.index[400]
    before = estimate_all(df, mid)
    poisoned = df.copy()
    poisoned.loc[poisoned.index >= mid,
                 ["Open", "High", "Low", "Close", "Volume"]] = 9e9
    after = estimate_all(poisoned, mid)
    assert before == after, f"CAUSALITY BREACH: {before} != {after}"
    ok += 1

    # 3) insufficient data -> None, never a number
    tiny = df.iloc[:3]
    t3 = df.index[3]
    for fn in (bar_range_proxy, corwin_schultz, abdi_ranaldo, roll,
               amihud):
        assert fn(tiny, t3) is None
        ok += 1

    # 4) no_trade_share on a half-empty tape ~= 0.5
    sparse = df.iloc[400:430:2]                  # every other minute
    tns = df.index[430]
    nts = no_trade_share(sparse, tns, window_min=30)
    assert nts is not None and 0.4 <= nts <= 0.6, f"no_trade_share {nts}"
    ok += 1

    # 5) amihud returns a positive finite number on real-shaped data
    ami = amihud(df, mid)
    assert ami is not None and ami > 0 and math.isfinite(ami)
    ok += 1

    print(f"liquidity_estimators self-test: {ok}/13 checks passed")


if __name__ == "__main__":
    self_test()
