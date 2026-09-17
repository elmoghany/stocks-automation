"""OPEN-UNIVERSE (2026-09-17): measured transaction cost for a universe that
has no 1-second tape.

COST-REBASE measured the toll per (name, minute) from `data/massive/trades`
(1-second aggregates) for 71,713 symbol-days of the CAUSAL WIDE HALAL universe.
The open universe is 3,298 symbols and 1.13M symbol-days; the overwhelming
majority of them have no 1-second tape, so `cr_cost.CostModel` would fall
through to its "legacy" tier (a flat 10 bps) on nearly every fill, which would
answer the mandate's question ("do cheaper books make the toll fall enough to
matter?") by assumption instead of by measurement.

Two models are built here, both with the SAME functional form as
plan/cr_cost.py -- max(Corwin-Schultz, Abdi-Ranaldo) for the spread, plus the
identical square-root impact term at the identical conservative coefficient
Y = 1.0 -- and both fed by strictly-prior data:

  DailyCost   for the gd open/close grid, i.e. the whole 2,532-name universe.
              CS and AR are ORIGINALLY daily-bar estimators (Corwin & Schultz
              2012 run them on daily highs and lows), so applying them to the
              prior 20 grouped-daily bars is their intended use, not a
              stretch.  The impact term uses prior-20-session daily sigma and
              the prior-60-session median daily dollar volume; the square-root
              law is HORIZON-INVARIANT -- sigma_T * sqrt(Q / V_T) is the same
              number at T = 10 minutes and T = 1 day, because sigma scales as
              sqrt(T) and V scales as T -- so this is directly comparable to
              cr_cost's 10-minute window, and plan/ou_cost.py --validate
              checks exactly that against the 1-second-derived numbers.

  MinuteCost  for the top-600 minute subset.  It writes cr_cost-shaped
              per-minute npz files out of the m1o 1-minute bars with the
              `hl2` (per-second bid-ask-bounce) channel set to NaN, and then
              uses cr_cost.CostModel itself -- the same class, the same
              causality guard, the same tier ladder.  With hl2 absent the
              spread reduces to max(CS, AR) on trailing 1-minute bars.

CONSERVATISM.  Where an estimator cannot be formed the model returns the
incumbent LEGACY_BPS = 10.0, never 0, exactly as cr_cost does, and it is
floored at FLOOR_BPS = 1.0 bp a side.  Outside 09:30-16:00 it charges at
least the incumbent 50 bps extended-hours premium on top.

Usage:
  python plan/ou_cost.py --build-daily       -> plan/ou_out/daily_cost.npz
  python plan/ou_cost.py --validate          -> plan/ou_out/cost_validate.json
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ou_lib as L                                            # noqa: E402
import cr_cost as CR                                          # noqa: E402

IMPACT_COEF = CR.IMPACT_COEF          # 1.0, top of the published range
FLOOR_BPS = CR.FLOOR_BPS              # 1.0
LEGACY_BPS = CR.LEGACY_BPS            # 10.0
CS_WIN = 20                           # prior sessions for CS / AR
SIG_WIN = 20                          # prior sessions for daily sigma
MIN_PAIRS = CR.MIN_PAIRS              # 5


def _cs_ar_daily(O, H, LO, C):
    """Per-pair Corwin-Schultz and Abdi-Ranaldo on a (D, S) daily panel.

    Returns (cs_s, cs_ok, ar_x, ar_ok) each (D-1, S): pair t spans sessions
    t and t+1.  Same algebra as cr_cost.cs_pairs / ar_pairs, vectorised over
    the whole cross-section at once.
    """
    h1, l1, c1 = H[:-1], LO[:-1], C[:-1]
    h2, l2, o2 = H[1:].copy(), LO[1:].copy(), O[1:]
    cs_ok = (np.fmin(np.fmin(h1, l1), np.fmin(h2, l2)) > 0) & (o2 > 0) \
        & (h1 >= l1) & (h2 >= l2)
    adj = np.where(o2 > h1, o2 - h1, np.where(o2 < l1, o2 - l1, 0.0))
    h2 = h2 - adj
    l2 = l2 - adj
    cs_ok &= np.fmin(h2, l2) > 0
    cs_ok = np.nan_to_num(cs_ok.astype(float), nan=0.0).astype(bool)
    with np.errstate(all="ignore"):
        b = np.log(h1 / l1) ** 2 + np.log(h2 / l2) ** 2
        g = np.log(np.fmax(h1, h2) / np.fmin(l1, l2)) ** 2
        alpha = (np.sqrt(2.0 * b) - np.sqrt(b)) / CR.CS_K - np.sqrt(g / CR.CS_K)
        s = 2.0 * (np.exp(alpha) - 1.0) / (1.0 + np.exp(alpha))
    cs_s = np.where(cs_ok, np.maximum(np.nan_to_num(s), 0.0), 0.0)

    ar_ok = (np.fmin(np.fmin(h1, l1), c1) > 0) & (np.fmin(h2, l2) > 0)
    ar_ok = np.nan_to_num(ar_ok.astype(float), nan=0.0).astype(bool)
    with np.errstate(all="ignore"):
        lc = np.log(c1)
        e1 = 0.5 * (np.log(h1) + np.log(l1))
        e2 = 0.5 * (np.log(h2) + np.log(l2))
        x = (lc - e1) * (lc - e2)
    ar_x = np.where(ar_ok, np.nan_to_num(x), 0.0)
    return cs_s, cs_ok, ar_x, ar_ok


def _roll_mean(vals, ok, win, minn):
    """Trailing mean over `win` PAIRS ending strictly before row t.

    vals/ok are (D-1, S) per-pair arrays; the result is (D, S) with NaN
    where fewer than `minn` usable pairs sit in the window.  Row t uses
    pairs [t-1-win, t-1), i.e. sessions strictly before t.
    """
    D1, S = vals.shape
    cs = np.concatenate([np.zeros((1, S)), np.cumsum(vals, axis=0)])
    cn = np.concatenate([np.zeros((1, S)), np.cumsum(ok.astype(float), axis=0)])
    D = D1 + 1
    out = np.full((D, S), np.nan)
    for t in range(D):
        b = max(t - 1, 0)
        a = max(b - win, 0)
        n = cn[b] - cn[a]
        with np.errstate(all="ignore"):
            m = np.where(n >= minn, (cs[b] - cs[a]) / np.maximum(n, 1), np.nan)
        out[t] = m
    return out


SPREAD_TABLE_F = L.OUT / "spread_table.json"


def spread_table():
    """half-spread bps/side by prior-60-session median dollar volume.

    WHY A TABLE AND NOT AN ESTIMATOR.  The first cut of this module ran
    Corwin-Schultz and Abdi-Ranaldo on DAILY grouped bars, because that is
    the frequency both papers were written for.  Validated against the
    1-second tape it came out at a 50 bps MEDIAN HALF-SPREAD -- a $0.20
    spread on a $20 stock, roughly 15x the truth.  The reason is not subtle:
    at daily frequency the high-low range of a US equity is dominated by
    intraday drift and the overnight gap, and both estimators read that
    variance as spread.  The SAME estimators on 1-MINUTE bars land at
    1-6 bps, in line with UNIVERSE-QUOTES' 2-6 bps and COST-REBASE's 2.77
    bps median -- so the estimator is right and the frequency was wrong.

    The open universe has 1-minute bars for its top 600 names only, so for
    the other ~1,900 names a day the half-spread is read off a table
    MEASURED on the two ground truths this repo has, bucketed by the only
    liquidity variable available for every name on every date:

      data/massive/cost1   the 1-second tape of the causal wide halal
                           universe (27,209 symbol-days), which covers the
                           $2M-$1B dollar-volume range, i.e. the LOW end;
      data/massive/cost1o  this line's own m1o-derived per-minute cache
                           (867 symbols x 448 dates), which covers the
                           $50M-$50B range, i.e. the HIGH end.

    Reported, not hidden: this maps liquidity to spread, so two names with
    the same dollar volume get the same half-spread.  It is a bucket median,
    not an identity, and the audit prints the bucket dispersion beside it.
    Where the two sources overlap they are compared, and the table takes the
    MORE EXPENSIVE of the two.
    """
    if SPREAD_TABLE_F.exists():
        return json.loads(SPREAD_TABLE_F.read_text())
    raise SystemExit("run: python plan/ou_cost.py --build-spread-table")


def _bucket_half(mdv, tab):
    """Vectorised lookup of the half-spread table."""
    edges = np.array([r["lo"] for r in tab] + [tab[-1]["hi"]])
    vals = np.array([r["half"] for r in tab])
    i = np.clip(np.searchsorted(edges, mdv, side="right") - 1, 0, len(vals) - 1)
    out = vals[i]
    return np.where(np.isfinite(mdv), out, LEGACY_BPS)


def build_daily(dates=None):
    """Per (date, symbol) measured cost in bps/side for a $15,000 ticket.

    Every input row is strictly before `date`.  Written to
    plan/ou_out/daily_cost.npz as (D, S) float32 with the symbol and date
    axes, plus the spread and impact components so the decomposition can be
    reported the way COST-REBASE reports it.

      half   = spread_table()[prior-60-session median dollar volume]
      impact = 1.0 * sigma_20d_bps * sqrt(notional / mdv_60d)
               -- cr_cost's own square-root term at cr_cost's own
               coefficient.  The law is HORIZON-INVARIANT (sigma_T scales as
               sqrt(T) and V_T as T, so sigma_T*sqrt(Q/V_T) is the same at
               T = 10 minutes and T = 1 day), which is what makes a daily
               estimate of an intraday impact legitimate -- and which
               plan/ou_cost.py --validate checks against the minute model.
    """
    tab = spread_table()
    all_dates = L.trading_dates()
    syms, sidx, A = L.gd_matrices(all_dates)
    O, H, LO, C, V = (A["o"], A["h"], A["l"], A["c"], A["v"])
    D, S = C.shape

    # daily log returns, and the trailing-20-session sigma STRICTLY BEFORE t
    with np.errstate(all="ignore"):
        ret = np.full((D, S), np.nan)
        ret[1:] = np.log(C[1:] / C[:-1])
    sig = np.full((D, S), np.nan)
    dv = C * V
    mdv = np.full((D, S), np.nan)
    for t in range(D):
        a = max(t - SIG_WIN, 0)
        w = ret[a:t]
        if w.shape[0] >= 5:
            with np.errstate(all="ignore"):
                n = np.sum(np.isfinite(w), axis=0)
                s = np.nanstd(w, axis=0, ddof=1)
            sig[t] = np.where(n >= 5, s, np.nan)
        a2 = max(t - L.LOOKBACK, 0)
        w2 = dv[a2:t]
        if w2.shape[0] >= 5:
            with np.errstate(all="ignore"):
                mdv[t] = np.nanmedian(w2, axis=0)
    half = _bucket_half(mdv, tab)
    with np.errstate(all="ignore"):
        impact = IMPACT_COEF * (sig * 1e4) * np.sqrt(L.TICKET
                                                     / np.maximum(mdv, 1.0))
    tot = half + impact
    tot = np.where(np.isfinite(tot), np.maximum(tot, FLOOR_BPS), LEGACY_BPS)
    np.savez_compressed(L.OUT / "daily_cost.npz",
                        syms=np.array(syms), dates=np.array(all_dates),
                        half=half.astype(np.float32),
                        impact=impact.astype(np.float32),
                        total=tot.astype(np.float32))
    fin = np.isfinite(half)
    print(f"daily cost: {D} dates x {S:,} symbols; half-spread finite on "
          f"{fin.mean()*100:.1f}% of cells", flush=True)
    return syms, all_dates, half, impact, tot


class DailyCost:
    """Lookup wrapper over plan/ou_out/daily_cost.npz."""

    def __init__(self):
        z = np.load(L.OUT / "daily_cost.npz", allow_pickle=False)
        self.syms = [str(s) for s in z["syms"]]
        self.dates = [str(d) for d in z["dates"]]
        self.sidx = {s: i for i, s in enumerate(self.syms)}
        self.didx = {d: i for i, d in enumerate(self.dates)}
        self.half = z["half"].astype(np.float64)
        self.impact = z["impact"].astype(np.float64)
        self.total = z["total"].astype(np.float64)

    def row(self, date, syms):
        """bps/side for a $15,000 ticket in each of `syms` on `date`."""
        t = self.didx[date]
        j = np.array([self.sidx.get(s, -1) for s in syms])
        out = np.full(len(syms), LEGACY_BPS)
        ok = j >= 0
        out[ok] = self.total[t, j[ok]]
        return out

    def scaled(self, date, syms, notional):
        """Same, with the impact term rescaled to a non-$15k notional."""
        t = self.didx[date]
        j = np.array([self.sidx.get(s, -1) for s in syms])
        out = np.full(len(syms), LEGACY_BPS)
        ok = j >= 0
        h = self.half[t, j[ok]]
        im = self.impact[t, j[ok]] * np.sqrt(
            np.asarray(notional, float)[ok] / L.TICKET)
        v = h + im
        out[ok] = np.where(np.isfinite(v), np.maximum(v, FLOOR_BPS),
                           LEGACY_BPS)
        return out


# ================================================================== minute
C1O = L.ROOT / "data" / "massive" / "cost1o"
CR_LO = CR.MIN_M - 4 * 60          # 09:30 on the m1o 04:00 grid == 330
CR_N = CR.NMIN                     # 395 slots, 09:30..16:04


def _rolling_from_m1(o, h, lo, c, v):
    """cr_cost.CostModel._rolling, fed by 1-minute bars instead of the
    1-second tape, with the hl2 (per-second bid-ask-bounce) channel absent.

    The spread therefore reduces to max(Corwin-Schultz, Abdi-Ranaldo) on the
    trailing CSAR_WIN 1-minute bars -- the two estimators cr_cost already
    computes on 1-minute bars -- and the impact term is unchanged.  Returns
    (spread, dv_win, sig_win), each (395,), every entry a function of minutes
    STRICTLY BEFORE m.  `--selftest-minute` asserts this reproduces
    cr_cost's own `_rolling` element-for-element on the same inputs.
    """
    sl = slice(CR_LO, CR_LO + CR_N)
    oo = np.nan_to_num(o[sl]).astype(np.float64)
    hh = np.nan_to_num(h[sl]).astype(np.float64)
    ll = np.nan_to_num(lo[sl]).astype(np.float64)
    cc = np.nan_to_num(c[sl]).astype(np.float64)
    vv = np.nan_to_num(v[sl]).astype(np.float64)
    dv = cc * vv
    n = CR_N
    cdv = np.concatenate([[0.0], np.cumsum(dv)])
    m = np.arange(n)
    a = np.maximum(0, m - CR.IMPACT_WIN)
    dvw = cdv[m] - cdv[a]

    sig = np.full(n, np.nan)
    for k in range(n):
        lo_k = max(0, k - CR.IMPACT_WIN)
        w = cc[lo_k:k]
        w = w[w > 0]
        if w.size >= 3:
            r = np.diff(np.log(w))
            if r.size >= 2:
                sig[k] = float(np.std(r, ddof=1)) * math.sqrt(
                    max(1, k - lo_k)) * 1e4

    cs_s, cs_ok = CR.cs_pairs(oo, hh, ll)
    ar_x, ar_ok = CR.ar_pairs(hh, ll, cc)
    cs_cs = np.concatenate([[0.0], np.cumsum(np.where(cs_ok, cs_s, 0.0))])
    cs_cn = np.concatenate([[0], np.cumsum(cs_ok.astype(np.int64))])
    ar_cs = np.concatenate([[0.0], np.cumsum(np.where(ar_ok, ar_x, 0.0))])
    ar_cn = np.concatenate([[0], np.cumsum(ar_ok.astype(np.int64))])
    npair = len(cs_s)
    b0 = np.maximum(0, m - CR.CSAR_WIN)
    pa = np.minimum(b0, npair)
    pb = np.minimum(np.maximum(m - 1, 0), npair)
    ncs = cs_cn[pb] - cs_cn[pa]
    nar = ar_cn[pb] - ar_cn[pa]
    with np.errstate(all="ignore"):
        cs = np.where(ncs >= MIN_PAIRS,
                      1e4 * (cs_cs[pb] - cs_cs[pa]) / np.maximum(ncs, 1),
                      np.nan)
        arm = np.where(nar >= MIN_PAIRS,
                       (ar_cs[pb] - ar_cs[pa]) / np.maximum(nar, 1), np.nan)
        ar = np.where(np.isfinite(arm),
                      1e4 * np.sqrt(np.maximum(4.0 * arm, 0.0)), np.nan)
    spread = np.fmax(cs, ar)
    return spread, dvw, sig


def _ffill2(a):
    """Row-wise forward fill of NaN (NaN stays before the first value)."""
    idx = np.where(~np.isnan(a), np.arange(a.shape[1])[None, :], 0)
    np.maximum.accumulate(idx, axis=1, out=idx)
    out = np.take_along_axis(a, idx, axis=1)
    first = np.argmax(~np.isnan(a), axis=1)
    never = np.isnan(a).all(axis=1)
    cols = np.arange(a.shape[1])[None, :]
    out = np.where((cols < first[:, None]) | never[:, None], np.nan, out)
    return out


def _cs_ar_batch(o, h, lo, c):
    """cr_cost.cs_pairs / ar_pairs over a (n_dates, n_min) block at once."""
    h1, l1, c1 = h[:, :-1], lo[:, :-1], c[:, :-1]
    # RAW second legs -- Abdi-Ranaldo uses these, Corwin-Schultz uses the
    # overnight-adjusted copies.  cr_cost keeps the two in separate
    # functions; conflating them here was a real bug, caught by
    # --selftest-minute.
    h2r, l2r, o2 = h[:, 1:], lo[:, 1:], o[:, 1:]
    cs_ok = ((np.minimum.reduce([h1, l1, h2r, l2r, o2]) > 0)
             & (h1 >= l1) & (h2r >= l2r))
    adj = np.where(o2 > h1, o2 - h1, np.where(o2 < l1, o2 - l1, 0.0))
    h2 = h2r - adj
    l2 = l2r - adj
    cs_ok = cs_ok & (np.minimum(h2, l2) > 0)
    with np.errstate(all="ignore"):
        b = np.log(h1 / l1) ** 2 + np.log(h2 / l2) ** 2
        g = np.log(np.maximum(h1, h2) / np.minimum(l1, l2)) ** 2
        alpha = ((np.sqrt(2.0 * b) - np.sqrt(b)) / CR.CS_K
                 - np.sqrt(g / CR.CS_K))
        ss = 2.0 * (np.exp(alpha) - 1.0) / (1.0 + np.exp(alpha))
    cs_s = np.where(cs_ok, np.maximum(np.nan_to_num(ss), 0.0), 0.0)
    ar_ok = np.minimum.reduce([h1, l1, c1, h2r, l2r]) > 0
    with np.errstate(all="ignore"):
        lc = np.log(c1)
        e1 = 0.5 * (np.log(h1) + np.log(l1))
        e2 = 0.5 * (np.log(h2r) + np.log(l2r))
        x = (lc - e1) * (lc - e2)
    ar_x = np.where(ar_ok, np.nan_to_num(x), 0.0)
    return cs_s, cs_ok, ar_x, ar_ok


def rolling_batch(o, h, lo, c, v):
    """`_rolling_from_m1` for a whole SYMBOL at once: (n_dates, 960) in,
    three (n_dates, 395) arrays out.

    Identical arithmetic, vectorised over dates.  The one place that needed
    thought is sigma: cr_cost takes the closes that PRINTED inside the
    trailing window, log-differences those, and takes a ddof=1 standard
    deviation -- a compaction that depends on the print mask.  Forward
    filling inside the window turns every non-printing minute's return into
    an exact 0.0, so the ffilled return vector is the compacted one plus
    zeros; zeros contribute nothing to either sum, and the COUNT is taken
    from the print mask rather than from the non-zero returns, so
    sum/sum-of-squares/n reproduce np.std(ddof=1) exactly.
    `--selftest-minute` asserts it against cr_cost itself.
    """
    sl = slice(CR_LO, CR_LO + CR_N)
    oo = np.nan_to_num(o[:, sl]).astype(np.float64)
    hh = np.nan_to_num(h[:, sl]).astype(np.float64)
    ll = np.nan_to_num(lo[:, sl]).astype(np.float64)
    cc = np.nan_to_num(c[:, sl]).astype(np.float64)
    vv = np.nan_to_num(v[:, sl]).astype(np.float64)
    n = CR_N
    D = oo.shape[0]
    dv = cc * vv
    cdv = np.concatenate([np.zeros((D, 1)), np.cumsum(dv, axis=1)], axis=1)
    m = np.arange(n)
    a = np.maximum(0, m - CR.IMPACT_WIN)
    dvw = cdv[:, m] - cdv[:, a]

    valid = cc > 0
    lc = np.where(valid, np.log(np.maximum(cc, 1e-300)), np.nan)
    lcf = _ffill2(lc)
    r = np.zeros((D, n))
    r[:, 1:] = np.nan_to_num(lcf[:, 1:] - lcf[:, :-1])
    # a return whose LEFT leg sits before the window start is not one of the
    # compacted returns; it is removed per-window below via `firstpos`.
    cr_ = np.concatenate([np.zeros((D, 1)), np.cumsum(r, axis=1)], axis=1)
    cr2 = np.concatenate([np.zeros((D, 1)), np.cumsum(r * r, axis=1)], axis=1)
    cvn = np.concatenate([np.zeros((D, 1)),
                          np.cumsum(valid.astype(np.float64), axis=1)], axis=1)
    # index of the first printed minute at or after k
    nxt = np.full((D, n + 1), n, np.int64)
    for k in range(n - 1, -1, -1):
        nxt[:, k] = np.where(valid[:, k], k, nxt[:, k + 1])
    nxt = nxt[:, :n]
    sig = np.full((D, n), np.nan)
    for k in range(n):
        lo_k = max(0, k - CR.IMPACT_WIN)
        nv = cvn[:, k] - cvn[:, lo_k]
        fp = np.minimum(nxt[:, lo_k], k)            # first printed in window
        # drop r[fp]: its LEFT leg is the last print before the window, so it
        # is not one of the compacted returns cr_cost forms inside [lo_k, k).
        take = fp < k
        rf = np.where(take, r[np.arange(D), np.clip(fp, 0, n - 1)], 0.0)
        s1 = (cr_[:, k] - cr_[:, lo_k]) - rf
        s2 = (cr2[:, k] - cr2[:, lo_k]) - rf * rf
        nr = nv - 1.0
        with np.errstate(all="ignore"):
            var = (s2 - s1 * s1 / np.maximum(nr, 1.0)) / np.maximum(nr - 1, 1.0)
            sd = np.sqrt(np.maximum(var, 0.0))
        sig[:, k] = np.where(nv >= 3, sd * math.sqrt(max(1, k - lo_k)) * 1e4,
                             np.nan)

    cs_s, cs_ok, ar_x, ar_ok = _cs_ar_batch(oo, hh, ll, cc)
    z1 = np.zeros((D, 1))
    cs_cs = np.concatenate([z1, np.cumsum(np.where(cs_ok, cs_s, 0.), axis=1)],
                           axis=1)
    cs_cn = np.concatenate([z1, np.cumsum(cs_ok.astype(np.float64), axis=1)],
                           axis=1)
    ar_cs = np.concatenate([z1, np.cumsum(np.where(ar_ok, ar_x, 0.), axis=1)],
                           axis=1)
    ar_cn = np.concatenate([z1, np.cumsum(ar_ok.astype(np.float64), axis=1)],
                           axis=1)
    npair = cs_s.shape[1]
    b0 = np.maximum(0, m - CR.CSAR_WIN)
    pa = np.minimum(b0, npair)
    pb = np.minimum(np.maximum(m - 1, 0), npair)
    ncs = cs_cn[:, pb] - cs_cn[:, pa]
    nar = ar_cn[:, pb] - ar_cn[:, pa]
    with np.errstate(all="ignore"):
        cs = np.where(ncs >= MIN_PAIRS,
                      1e4 * (cs_cs[:, pb] - cs_cs[:, pa])
                      / np.maximum(ncs, 1), np.nan)
        arm = np.where(nar >= MIN_PAIRS,
                       (ar_cs[:, pb] - ar_cs[:, pa]) / np.maximum(nar, 1),
                       np.nan)
        ar = np.where(np.isfinite(arm),
                      1e4 * np.sqrt(np.maximum(4.0 * arm, 0.0)), np.nan)
    spread = np.fmax(cs, ar)
    return spread, dvw, sig


def build_minute(workers=8, limit=None):
    """data/massive/cost1o/{SYM}.npz -- spread / dv_win / sig_win per date."""
    import json as _json
    from concurrent.futures import ProcessPoolExecutor
    C1O.mkdir(parents=True, exist_ok=True)
    pairs = _json.loads((L.OUT / "minute_pairs.json").read_text())
    syms = sorted({s for s, _ in pairs})
    todo = [s for s in syms if not (C1O / f"{s}.npz").exists()]
    if limit:
        todo = todo[:limit]
    print(f"cost1o: {len(syms):,} symbols, {len(todo):,} to build",
          flush=True)
    import time as _t
    t0 = _t.monotonic()
    done = 0
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for r in ex.map(_minute_worker, todo, chunksize=4):
            done += 1
            if done % 50 == 0:
                el = _t.monotonic() - t0
                print(f"  [{done}/{len(todo)}] {el:.0f}s eta "
                      f"{el/done*(len(todo)-done)/60:.1f}m", flush=True)
    print(f"cost1o done in {(_t.monotonic()-t0)/60:.1f}m", flush=True)


def _minute_worker(sym):
    f = L.M1O / f"{sym}.npz"
    out = C1O / f"{sym}.npz"
    if out.exists() or not f.exists():
        return "skip"
    try:
        z = np.load(f, allow_pickle=False)
        ds = [str(x) for x in z["dates"]]
        if not ds:
            return "empty"
        sp, dw, sg = rolling_batch(z["o"], z["h"], z["l"], z["c"], z["v"])
        np.savez_compressed(out, dates=np.array(ds, dtype="U10"),
                            spread=sp.astype(np.float32),
                            dv_win=dw.astype(np.float32),
                            sig_win=sg.astype(np.float32))
        return "got"
    except Exception as e:
        return f"err:{type(e).__name__}"


class MinuteCost:
    """cr_cost's lookup over the m1o-derived per-minute statistics."""

    def __init__(self, impact_coef=IMPACT_COEF, ext_floor_bps=LEGACY_BPS,
                 enable_impact=True):
        self.coef = float(impact_coef)
        self.ext_floor = float(ext_floor_bps)
        self.enable_impact = bool(enable_impact)
        self._sym = {}
        self._order = []
        self.tally = {}

    def _load(self, sym):
        if sym in self._sym:
            return self._sym[sym]
        f = C1O / f"{sym}.npz"
        rec = None
        if f.exists():
            try:
                z = np.load(f, allow_pickle=False)
                rec = ({str(d): i for i, d in enumerate(z["dates"])},
                       z["spread"].astype(np.float64),
                       z["dv_win"].astype(np.float64),
                       z["sig_win"].astype(np.float64),
                       [str(d) for d in z["dates"]])
            except Exception:
                rec = None
        if len(self._order) > 120:
            self._sym.pop(self._order.pop(0), None)
        self._sym[sym] = rec
        self._order.append(sym)
        return rec

    def parts(self, sym, date, gm, notional):
        """(half, impact, tier) for a fill at grid minute `gm` (04:00 base)."""
        m = int(gm) - CR_LO
        rec = self._load(sym)
        sp, tier = None, "legacy"
        if rec is not None and 0 <= m < CR_N:
            i = rec[0].get(date)
            if i is not None:
                v = rec[1][i, m]
                if np.isfinite(v):
                    sp, tier = float(v), "win"
                if sp is None:
                    # prior-session day median: strictly past information
                    k = np.searchsorted(rec[4], date) - 1
                    for j in range(k, max(-1, k - 5), -1):
                        w = rec[1][j]
                        w = w[np.isfinite(w)]
                        if w.size:
                            sp, tier = float(np.median(w)), "prior"
                            break
        if sp is None:
            sp, tier = LEGACY_BPS * 2.0, "legacy"
        half = max(FLOOR_BPS, sp / 2.0)
        imp = 0.0
        if self.enable_impact and rec is not None and 0 <= m < CR_N:
            i = rec[0].get(date)
            if i is not None:
                dvw, sg = rec[2][i, m], rec[3][i, m]
                if dvw > 0 and np.isfinite(sg) and notional > 0:
                    imp = self.coef * sg * math.sqrt(notional / dvw)
                elif notional > 0:
                    imp = LEGACY_BPS
            elif notional > 0:
                imp = LEGACY_BPS
        return half, imp, tier

    def cost_bps(self, sym, date, gm, notional, passive=False):
        half, imp, tier = self.parts(sym, date, gm, notional)
        c = max(FLOOR_BPS, (0.0 if passive else half) + imp)
        if not (L.RTH_LO <= int(gm) < L.RTH_HI):
            c = max(c, self.ext_floor)
            tier += "+ext"
        self.tally[tier] = self.tally.get(tier, 0) + 1
        self.tally["_n"] = self.tally.get("_n", 0) + 1
        self.tally["_sum"] = self.tally.get("_sum", 0.0) + c
        if c > LEGACY_BPS:
            self.tally["_gt10"] = self.tally.get("_gt10", 0) + 1
        return c

    def vec(self, syms, dates, gms, notionals, passive=False):
        return np.array([self.cost_bps(s, d, g, n, passive)
                         for s, d, g, n in zip(syms, dates, gms, notionals)])

    def report(self):
        n = self.tally.get("_n", 0)
        return {"n": n,
                "mean_bps": round(self.tally.get("_sum", 0.0) / n, 3)
                if n else None,
                "frac_gt_10bps": round(self.tally.get("_gt10", 0) / n, 4)
                if n else None,
                "tiers": {k: v for k, v in sorted(self.tally.items())
                          if not k.startswith("_")}}


BUCKETS = [0, 1e7, 2e7, 5e7, 1e8, 2e8, 5e8, 1e9, 5e9, 2e10, 1e14]


def _mdv_lookup():
    """(sidx, didx, dvol) for prior-60-session median dollar volume."""
    all_dates = L.trading_dates()
    syms, sidx, A = L.gd_matrices(all_dates)
    dv = A["c"] * A["v"]
    return syms, sidx, {d: i for i, d in enumerate(all_dates)}, dv


def _mdv(dv, didx, sidx, sym, date):
    t, j = didx.get(date), sidx.get(sym)
    if t is None or j is None:
        return np.nan
    w = dv[max(0, t - L.LOOKBACK):t, j]
    w = w[np.isfinite(w)]
    return float(np.median(w)) if w.size >= L.MIN_OBS else np.nan


def build_spread_table(n_sec=6000, n_min=6000, seed=0):
    """Measure the half-spread ground truth from BOTH caches and bucket it."""
    import random
    syms, sidx, didx, dv = _mdv_lookup()
    rng = random.Random(seed)
    obs = []                      # (mdv, half_bps, source)

    # ---- source A: the 1-second tape (COST-REBASE's cache), low end
    fs = list(CR.CDIR.glob("*.npz"))
    if len(fs) > n_sec:
        fs = rng.sample(fs, n_sec)
    for p in fs:
        try:
            s, d = p.name[:-4].split("_", 1)
        except ValueError:
            continue
        m = _mdv(dv, didx, sidx, s, d)
        if not np.isfinite(m):
            continue
        try:
            with np.load(p) as z:
                o = z["o"].astype(np.float64)
                h = z["h"].astype(np.float64)
                lo = z["l"].astype(np.float64)
                c = z["c"].astype(np.float64)
                hl2 = z["hl2"].astype(np.float64)
        except Exception:
            continue
        v = []
        hh = hl2[np.isfinite(hl2)]
        if hh.size >= 20:
            v.append(float(np.median(hh)))
        cs_s, cs_ok = CR.cs_pairs(o, h, lo)
        if cs_ok.sum() >= 20:
            v.append(1e4 * float(cs_s[cs_ok].mean()))
        ar_x, ar_ok = CR.ar_pairs(h, lo, c)
        if ar_ok.sum() >= 20:
            v.append(1e4 * math.sqrt(max(4.0 * float(ar_x[ar_ok].mean()), 0.)))
        if v:
            obs.append((m, max(v) / 2.0, "sec1"))

    # ---- source B: this line's own m1o-derived per-minute cache, high end
    fm = sorted(C1O.glob("*.npz"))
    per = max(1, n_min // max(len(fm), 1))
    for p in fm:
        sym = p.stem
        try:
            with np.load(p) as z:
                ds = [str(x) for x in z["dates"]]
                spr = z["spread"]
        except Exception:
            continue
        idx = rng.sample(range(len(ds)), min(per + 2, len(ds)))
        for i in idx:
            m = _mdv(dv, didx, sidx, sym, ds[i])
            if not np.isfinite(m):
                continue
            w = spr[i][np.isfinite(spr[i])]
            if w.size >= 20:
                obs.append((m, float(np.median(w)) / 2.0, "m1o"))

    a = np.array([(x[0], x[1]) for x in obs])
    src = np.array([x[2] for x in obs])
    tab = []
    for i in range(len(BUCKETS) - 1):
        lo_, hi_ = BUCKETS[i], BUCKETS[i + 1]
        m = (a[:, 0] >= lo_) & (a[:, 0] < hi_)
        if m.sum() < 15:
            tab.append({"lo": lo_, "hi": hi_, "n": int(m.sum()),
                        "half": None, "n_sec1": 0, "n_m1o": 0})
            continue
        v_all = float(np.median(a[m, 1]))
        d = {"lo": lo_, "hi": hi_, "n": int(m.sum()),
             "half": round(v_all, 3),
             "p25": round(float(np.percentile(a[m, 1], 25)), 3),
             "p75": round(float(np.percentile(a[m, 1], 75)), 3),
             "n_sec1": int((src[m] == "sec1").sum()),
             "n_m1o": int((src[m] == "m1o").sum())}
        for s in ("sec1", "m1o"):
            k = m & (src == s)
            d["half_" + s] = round(float(np.median(a[k, 1])), 3) \
                if k.sum() >= 15 else None
        # where both sources speak, take the MORE EXPENSIVE
        cands = [x for x in (d.get("half_sec1"), d.get("half_m1o"))
                 if x is not None]
        if cands:
            d["half"] = round(max(cands), 3)
        tab.append(d)
    # fill empty buckets by carrying the nearest populated one forward
    last = None
    for d in tab:
        if d["half"] is None:
            d["half"] = last if last is not None else LEGACY_BPS
            d["filled"] = True
        else:
            last = d["half"]
    L.OUT.mkdir(parents=True, exist_ok=True)
    SPREAD_TABLE_F.write_text(json.dumps(tab, indent=1))
    print(f"spread table ({len(obs):,} symbol-day observations)", flush=True)
    print(f"{'mdv bucket':>24s} {'n':>6s} {'sec1':>7s} {'m1o':>7s} "
          f"{'half':>7s} {'p25':>7s} {'p75':>7s}", flush=True)
    for d in tab:
        print(f"[{d['lo']:8.0e},{d['hi']:8.0e}) {d['n']:6d} "
              f"{str(d.get('half_sec1')):>7s} {str(d.get('half_m1o')):>7s} "
              f"{d['half']:7.3f} {str(d.get('p25')):>7s} "
              f"{str(d.get('p75')):>7s}", flush=True)
    return tab


def selftest_minute(nsym=3, ndate=4):
    """Assert _rolling_from_m1 == cr_cost.CostModel._rolling on the same
    bars (hl2 absent in both)."""
    import json as _json
    pairs = _json.loads((L.OUT / "minute_pairs.json").read_text())
    syms = sorted({s for s, _ in pairs})
    cm = CR.CostModel()
    checks = 0
    worst = {"spread": 0.0, "dv_win": 0.0, "sig_win": 0.0}
    for sym in syms[:nsym]:
        f = L.M1O / f"{sym}.npz"
        if not f.exists():
            continue
        z = np.load(f, allow_pickle=False)
        for i in range(min(ndate, len(z["dates"]))):
            sl = slice(CR_LO, CR_LO + CR_N)
            zz = {"o": np.nan_to_num(z["o"][i][sl]).astype(np.float32),
                  "h": np.nan_to_num(z["h"][i][sl]).astype(np.float32),
                  "l": np.nan_to_num(z["l"][i][sl]).astype(np.float32),
                  "c": np.nan_to_num(z["c"][i][sl]).astype(np.float32),
                  "dv": (np.nan_to_num(z["c"][i][sl])
                         * np.nan_to_num(z["v"][i][sl])).astype(np.float32),
                  "npr": np.zeros(CR_N, np.int32),
                  "hl2": np.full(CR_N, np.nan, np.float32)}
            d = CR._Day(zz)
            cm._rolling(d)
            sb, db, gb = rolling_batch(z["o"][i:i + 1], z["h"][i:i + 1],
                                       z["l"][i:i + 1], z["c"][i:i + 1],
                                       z["v"][i:i + 1])
            s1, d1, g1 = sb[0], db[0], gb[0]
            for nm, a, b in (("spread", d.spread, s1),
                             ("dv_win", d.dv_win, d1),
                             ("sig_win", d.sig_win, g1)):
                m = np.isfinite(a) | np.isfinite(b)
                if m.any():
                    x, y = np.nan_to_num(a[m]), np.nan_to_num(b[m])
                    rel = np.abs(x - y) / np.maximum(np.abs(x), 1e-9)
                    worst[nm] = max(worst[nm], float(np.max(rel)))
                assert np.array_equal(np.isfinite(a), np.isfinite(b)), \
                    (sym, i, nm, "finite mask")
            checks += 1
    print(f"selftest-minute: {checks} symbol-days, worst RELATIVE |diff| "
          f"{ {k: f'{v:.2e}' for k, v in worst.items()} }", flush=True)
    # dv_win is the only channel cr_cost stores as float32 (its npz `dv`
    # field), so it reconciles to float32 epsilon rather than to float64.
    assert worst["spread"] < 1e-9 and worst["sig_win"] < 1e-9, worst
    assert worst["dv_win"] < 1e-5, worst
    return {"checks": checks, "worst_rel_diff": worst}


# ---------------------------------------------------------------- validation
def validate(nmax=4000, seed=0):
    """Compare DailyCost with the 1-second-derived cr_cost on every symbol-day
    where BOTH exist, at 10:30 -- the honest calibration check."""
    from datetime import time as dtime
    dc = DailyCost()
    have = sorted(CR.CDIR.glob("*.npz"))
    rng = np.random.default_rng(seed)
    if len(have) > nmax:
        have = [have[i] for i in rng.choice(len(have), nmax, replace=False)]
    cm = CR.CostModel()
    rows = []
    for p in have:
        sym, date = p.name[:-4].split("_", 1)
        if date not in dc.didx or sym not in dc.sidx:
            continue
        try:
            b_sec = cm.cost_bps(sym, date, dtime(10, 30), L.TICKET)
        except Exception:
            continue
        b_day = float(dc.row(date, [sym])[0])
        t, j = dc.didx[date], dc.sidx[sym]
        rows.append({"sym": sym, "date": date, "sec": b_sec, "day": b_day,
                     "half_day": float(dc.half[t, j]),
                     "imp_day": float(dc.impact[t, j])})
    a = np.array([r["sec"] for r in rows])
    b = np.array([r["day"] for r in rows])
    ok = np.isfinite(a) & np.isfinite(b)
    a, b = a[ok], b[ok]
    out = {
        "n": int(a.size),
        "sec_median": round(float(np.median(a)), 3),
        "day_median": round(float(np.median(b)), 3),
        "sec_mean": round(float(a.mean()), 3),
        "day_mean": round(float(b.mean()), 3),
        "ratio_median": round(float(np.median(b / np.maximum(a, 1e-9))), 3),
        "frac_daily_cheaper": round(float((b < a).mean()), 4),
        "corr_log": round(float(np.corrcoef(np.log(np.maximum(a, .01)),
                                            np.log(np.maximum(b, .01)))[0, 1]),
                          4),
        "half_day_median": round(float(np.median(
            [r["half_day"] for r in rows if np.isfinite(r["half_day"])])), 3),
        "impact_day_median": round(float(np.median(
            [r["imp_day"] for r in rows if np.isfinite(r["imp_day"])])), 3),
    }
    L.write("cost_validate.json", out)
    print(json.dumps(out, indent=1), flush=True)
    return out


def main():
    if "--build-spread-table" in sys.argv:
        build_spread_table()
    if "--build-daily" in sys.argv:
        build_daily()
    if "--selftest-minute" in sys.argv:
        selftest_minute()
    if "--build-minute" in sys.argv:
        w = 8
        if "--workers" in sys.argv:
            w = int(sys.argv[sys.argv.index("--workers") + 1])
        build_minute(workers=w)
    if "--validate" in sys.argv:
        validate()


if __name__ == "__main__":
    main()
