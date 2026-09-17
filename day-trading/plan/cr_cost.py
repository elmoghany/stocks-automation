"""COST-REBASE (2026-09-16) -- a MEASURED, causal, per-name per-minute
transaction-cost model, to replace the project-wide flat 10 bps/side.

WHY. Every result in this repo since the gapper campaigns charges 10
bps a side (+50 bps outside 09:30-16:00). UNIVERSE-QUOTES measured the
real inside spread on the causal wide universe at 2-6 bps
(universe-quotes-audit.md Part 5) from the entitled 1-second aggregates
(/v3/quotes and /v3/trades are 403 on this account). On a $15,000
ticket the difference between a 10 bps and a 3 bps half-spread is about
$19 a round trip -- larger than any edge any model in this repo has
demonstrated. This module turns that observation into a per-fill number
that can be swapped in behind a flag.

WHAT IS MEASURED, AND FROM WHAT
  data/massive/trades/{SYM}_{DATE}.json.gz  (plan/uq_sec1.py's cache)
  rows = [[t_ms, o, h, l, c, v, n], ...], 1-second bars, 09:30-16:05 ET,
  adjusted.  `n` is the transaction count in that second, so a second
  with n >= 2 brackets the inside quote: its (high-low)/mid is an
  observation of the bid-ask bounce (biased DOWN when both prints land
  on the same side, biased UP by drift).

  Per (symbol, day, minute) this module stores sufficient statistics
  (plan/cr_cost.py --build), and per FILL it forms, from a TRAILING
  window that never touches the fill minute:

    spread_bps = max( HL2 , CS , AR )          (conservative of three)
      HL2 = median over the last SPREAD_WIN minutes of the per-minute
            median (high-low)/mid of seconds with n >= MIN_N2 prints
      CS  = Corwin-Schultz (2012) on the trailing CSAR_WIN 1-minute
            bars built from the same tape
      AR  = Abdi-Ranaldo (2017) on the same bars
      (Roll (1984) is computed and REPORTED but not used in the max:
       its median on this data is 18.6 bps, three times every other
       estimator, which is the known high-frequency breakdown of the
       serial-covariance estimator. Excluding it is the one judgement
       call in this model and it is stated here, not buried.)

    half_spread_bps = spread_bps / 2, floored at FLOOR_BPS

    impact_bps = IMPACT_COEF * sigma_win_bps * sqrt(notional / DV_win)
      DV_win      = trailing IMPACT_WIN minutes of dollar volume
      sigma_win   = stdev of 1-minute log returns over the same window,
                    scaled to the window horizon, in bps
      IMPACT_COEF = 1.0  -- the square-root law's Y, at the TOP of the
                    published range (Almgren et al. 2005 and the
                    Torre/BARRA line put Y at roughly 0.3-1.0), i.e.
                    deliberately conservative.
      The form is horizon-invariant: sigma_T * sqrt(Q/V_T) is the same
      number whether T is 10 minutes or a day, because sigma scales as
      sqrt(T) and V as T.

    cost_bps(side) = max(FLOOR_BPS, half_spread_bps + impact_bps)

CAUSALITY CONTRACT (plan/causal.py / liquidity_estimators.py discipline)
  Every window ENDS STRICTLY BEFORE the fill minute. The fill bar's own
  range is a consequence of our own trigger and is never read. The
  guard is asserted on every lookup, and plan/cr_poison.py mutates the
  whole tape at and after the fill minute and asserts not one cost
  moves.

CONSERVATISM WHERE THE DATA IS THIN (the mandate's guardrail)
  A minute with no prints contributes nothing; the window simply holds
  fewer minutes. The tier ladder, in order, never returns 0:
    1  tape, trailing SPREAD_WIN minutes           (tier "win")
    2  tape, trailing WIDE_WIN minutes             (tier "wide")
    3  the PRIOR session's day-median for the same symbol, which is
       strictly past information                   (tier "prior")
    4  LEGACY_BPS = 10.0, the incumbent assumption (tier "legacy")
  Tier 4 is the same number the incumbent ladder charges everywhere, so
  a symbol-day with no tape is priced exactly as it is priced today.
  `cost_report()` returns the tier mix and the fraction of fills where
  the measured cost EXCEEDS 10 bps, so the rebase cannot be
  one-directional by construction.

EXTENDED HOURS
  The tape is 09:30-16:05 only, so nothing outside the regular session
  is measured here. `cost_bps()` charges max(measured, ext_floor_bps)
  outside [09:30, 16:00), ext_floor_bps defaulting to the incumbent
  slippage. In the engine wrapper the 50 bps premarket haircut
  (`pm_spread_bps`) is left switched on ON TOP of that, so extended
  hours is never cheaper under the measured model than under the flat
  one.

USAGE
  python plan/cr_cost.py --build --pairs FILE [--workers 4]
  python plan/cr_cost.py --selftest
  from cr_cost import CostModel
  cm = CostModel()
  bps = cm.cost_bps("AAOI", "2026-08-05", dtime(10, 5), 15000.0)
"""

import gzip
import json
import math
import os
import sys
import time
from bisect import bisect_left
from datetime import datetime, time as dtime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
ET = ZoneInfo("America/New_York")

XDIR = ROOT / "data" / "massive" / "trades"        # 1-second tape
CDIR = ROOT / "data" / "massive" / "cost1"         # per-minute stats
OUT = HERE / "cr_out"

# ---- model constants (every one of them stated, none tuned on P&L) ----
SPREAD_WIN = 5          # minutes, primary trailing spread window
WIDE_WIN = 30           # minutes, widened fallback
CSAR_WIN = 30           # minutes of 1-minute bars for CS / AR
IMPACT_WIN = 10         # minutes, trailing dollar volume + vol
IMPACT_COEF = 1.0       # square-root-law Y, top of the published range
FLOOR_BPS = 1.0         # never charge less than 1 bp a side
LEGACY_BPS = 10.0       # the incumbent assumption = the last-resort tier
MIN_N2 = 2              # prints in a second before its range is usable
MIN_MIN_HL2 = 2         # minutes with an HL2 before the window counts
MIN_PAIRS = 5           # CS / AR pairs (same as liquidity_estimators)
SQ2 = math.sqrt(2.0)
CS_K = 3.0 - 2.0 * SQ2

MIN_M = 9 * 60 + 30     # 09:30 -> minute index 0
MAX_M = 16 * 60 + 5     # 16:05
NMIN = MAX_M - MIN_M    # 395 minute slots

RTH_LO = dtime(9, 30)
RTH_HI = dtime(16, 0)


def mkey(t):
    """minute-of-day -> index into the per-day arrays (or -1)."""
    m = t.hour * 60 + t.minute - MIN_M
    return m if 0 <= m < NMIN else -1


# ======================================================================
# stage 1 -- per (symbol, day) per-minute sufficient statistics
# ======================================================================

def _stats_from_rows(rows, date, base_hm=(9, 30), nmin=None):
    """rows -> per-minute arrays.  Pure function of the tape.

    Returns dict of float32/int32 arrays of length NMIN:
      o,h,l,c   1-minute OHLC built from the seconds (0 where no print)
      dv        dollar volume in the minute (sum of v * typical price)
      npr       transactions in the minute
      hl2       median (high-low)/mid in bps over seconds with n>=MIN_N2
                (NaN when the minute has fewer than one such second)
    """
    NM = NMIN if nmin is None else int(nmin)
    o = np.zeros(NM, np.float64)
    h = np.zeros(NM, np.float64)
    lo = np.zeros(NM, np.float64)
    c = np.zeros(NM, np.float64)
    dv = np.zeros(NM, np.float64)
    npr = np.zeros(NM, np.int64)
    hl2 = np.full(NM, np.nan, np.float64)
    if not rows:
        return dict(o=o, h=h, l=lo, c=c, dv=dv, npr=npr, hl2=hl2)
    a = np.asarray(rows, dtype=np.float64)
    t_ms = a[:, 0]
    # minute index straight off the epoch ms -- ET offset from the date
    y, mo, d = (int(x) for x in date.split("-"))
    base = datetime(y, mo, d, base_hm[0], base_hm[1],
                    tzinfo=ET).timestamp() * 1000.0
    mi = np.floor((t_ms - base) / 60000.0).astype(np.int64)
    ok = (mi >= 0) & (mi < NM)
    a, mi = a[ok], mi[ok]
    if not len(a):
        return dict(o=o, h=h, l=lo, c=c, dv=dv, npr=npr, hl2=hl2)
    so, sh, sl, sc, sv, sn = (a[:, 1], a[:, 2], a[:, 3], a[:, 4],
                              a[:, 5], a[:, 6])
    tp = (sh + sl + sc) / 3.0
    np.add.at(dv, mi, sv * tp)
    np.add.at(npr, mi, sn.astype(np.int64))
    # OHLC: rows are ascending, so first/last per minute give O/C
    first = np.ones(len(mi), bool)
    first[1:] = mi[1:] != mi[:-1]
    last = np.ones(len(mi), bool)
    last[:-1] = mi[:-1] != mi[1:]
    o[mi[first]] = so[first]
    c[mi[last]] = sc[last]
    np.maximum.at(h, mi, sh)
    lo[:] = np.inf
    np.minimum.at(lo, mi, sl)
    lo[~np.isfinite(lo)] = 0.0
    # per-second range on seconds with >= MIN_N2 prints, in bps
    sel = sn >= MIN_N2
    if sel.any():
        mid = (sh[sel] + sl[sel]) / 2.0
        good = mid > 0
        rng = np.zeros(good.sum())
        rng[:] = (sh[sel][good] - sl[sel][good]) / mid[good] * 1e4
        msel = mi[sel][good]
        order = np.argsort(msel, kind="stable")
        msel, rng = msel[order], rng[order]
        bounds = np.searchsorted(msel, np.arange(NM + 1))
        for k in range(NM):
            a0, a1 = bounds[k], bounds[k + 1]
            if a1 > a0:
                hl2[k] = float(np.median(rng[a0:a1]))
    return dict(o=o, h=h, l=lo, c=c, dv=dv, npr=npr, hl2=hl2)


def cfile(sym, date):
    return CDIR / f"{sym}_{date}.npz"


_IDX = [None]


def _index():
    """symbol -> sorted list of dates present in the per-minute cache.

    Built once by scanning the directory. Globbing per symbol over a
    27k-file directory was the dominant cost of the prior-session
    fallback."""
    if _IDX[0] is None:
        d = {}
        for p in CDIR.glob("*.npz"):
            s, dt = p.name[:-4].split("_", 1)
            d.setdefault(s, []).append(dt)
        for v in d.values():
            v.sort()
        _IDX[0] = d
    return _IDX[0]


def build_one(sym, date, force=False):
    f = cfile(sym, date)
    if f.exists() and not force:
        return "hit"
    src = XDIR / f"{sym}_{date}.json.gz"
    if not src.exists():
        return "notape"
    try:
        with gzip.open(src, "rt") as h:
            rows = json.load(h)["rows"]
    except Exception:
        return "bad"
    st = _stats_from_rows(rows, date)
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(f".npz.{os.getpid()}.part")
    np.savez_compressed(
        tmp, o=st["o"].astype(np.float32), h=st["h"].astype(np.float32),
        l=st["l"].astype(np.float32), c=st["c"].astype(np.float32),
        dv=st["dv"].astype(np.float32), npr=st["npr"].astype(np.int32),
        hl2=st["hl2"].astype(np.float32))
    os.replace(str(tmp) + ".npz" if not str(tmp).endswith(".npz") else tmp, f)
    return "got" if rows else "empty"


# ======================================================================
# stage 2 -- the estimators (vectorised; cross-checked in --selftest
#            against plan/liquidity_estimators.py's reference code)
# ======================================================================

def cs_pairs(o, h, l):
    """Vectorised Corwin-Schultz PER PAIR.

    Pair i is (bar i, bar i+1). Returns (s, ok) where s[i] is that
    pair's spread estimate as a FRACTION (floored at 0 per the paper's
    Section II.C correction) and ok[i] says the pair was usable. The
    windowed estimator is then a cumulative-sum mean over pairs, which
    turns the O(minutes x window) Python loop into O(minutes). Proved
    identical to `cs_bps` (and therefore to
    plan/liquidity_estimators.py's reference) in --selftest.
    """
    h1, l1 = h[:-1], l[:-1]
    h2, l2, o2 = h[1:].copy(), l[1:].copy(), o[1:]
    ok = ((np.minimum.reduce([h1, l1, h2, l2, o2]) > 0)
          & (h1 >= l1) & (h2 >= l2))
    adj = np.where(o2 > h1, o2 - h1, np.where(o2 < l1, o2 - l1, 0.0))
    h2 = h2 - adj
    l2 = l2 - adj
    ok &= np.minimum(h2, l2) > 0
    s = np.zeros(len(h1))
    if ok.any():
        with np.errstate(divide="ignore", invalid="ignore"):
            b = (np.log(h1[ok] / l1[ok]) ** 2
                 + np.log(h2[ok] / l2[ok]) ** 2)
            g = np.log(np.maximum(h1[ok], h2[ok])
                       / np.minimum(l1[ok], l2[ok])) ** 2
            alpha = ((np.sqrt(2.0 * b) - np.sqrt(b)) / CS_K
                     - np.sqrt(g / CS_K))
            ss = 2.0 * (np.exp(alpha) - 1.0) / (1.0 + np.exp(alpha))
        s[ok] = np.maximum(np.nan_to_num(ss), 0.0)
    return s, ok


def ar_pairs(h, l, c):
    """Vectorised Abdi-Ranaldo per pair: x[i] and its usability."""
    h1, l1, c1 = h[:-1], l[:-1], c[:-1]
    h2, l2 = h[1:], l[1:]
    ok = np.minimum.reduce([h1, l1, c1, h2, l2]) > 0
    x = np.zeros(len(h1))
    if ok.any():
        with np.errstate(divide="ignore", invalid="ignore"):
            lc = np.log(c1[ok])
            e1 = 0.5 * (np.log(h1[ok]) + np.log(l1[ok]))
            e2 = 0.5 * (np.log(h2[ok]) + np.log(l2[ok]))
            x[ok] = (lc - e1) * (lc - e2)
    return np.nan_to_num(x), ok


def _win_mean(csum, ccnt, a, b, minn):
    """mean over [a, b) from cumulative sums; None if fewer than minn."""
    n = ccnt[b] - ccnt[a]
    if n < minn:
        return None
    return (csum[b] - csum[a]) / n


def cs_bps(o, h, l, i0, i1):
    """Corwin-Schultz over 1-minute bars [i0, i1). Percent*100 = bps."""
    hh, ll, oo = h[i0:i1], l[i0:i1], o[i0:i1]
    n = len(hh)
    if n < 2:
        return None
    sp = []
    for i in range(n - 1):
        h1, l1 = hh[i], ll[i]
        h2, l2, o2 = hh[i + 1], ll[i + 1], oo[i + 1]
        if min(h1, l1, h2, l2, o2) <= 0 or h1 < l1 or h2 < l2:
            continue
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
        sp.append(max(s, 0.0))
    if len(sp) < MIN_PAIRS:
        return None
    return 1e4 * sum(sp) / len(sp)


def ar_bps(h, l, c, i0, i1):
    """Abdi-Ranaldo over 1-minute bars [i0, i1), in bps."""
    hh, ll, cc = h[i0:i1], l[i0:i1], c[i0:i1]
    n = len(hh)
    if n < 2:
        return None
    xs = []
    for i in range(n - 1):
        if min(hh[i], ll[i], cc[i], hh[i + 1], ll[i + 1]) <= 0:
            continue
        lc = math.log(cc[i])
        e1 = 0.5 * (math.log(hh[i]) + math.log(ll[i]))
        e2 = 0.5 * (math.log(hh[i + 1]) + math.log(ll[i + 1]))
        xs.append((lc - e1) * (lc - e2))
    if len(xs) < MIN_PAIRS:
        return None
    return 1e4 * math.sqrt(max(4.0 * sum(xs) / len(xs), 0.0))


def roll_bps(c, i0, i1):
    """Roll (1984), in bps -- REPORTED, not used in the max."""
    cc = c[i0:i1]
    cc = cc[cc > 0]
    if len(cc) < 10:
        return None
    r = np.diff(np.log(cc))
    if len(r) < 8:
        return None
    a, b = r[1:], r[:-1]
    cov = float(np.mean((a - a.mean()) * (b - b.mean())))
    if cov >= 0:
        return 0.0
    return 1e4 * 2.0 * math.sqrt(-cov)


# ======================================================================
# stage 3 -- the model
# ======================================================================

class _Day:
    """One symbol-day's per-minute statistics + cached rolling values."""

    __slots__ = ("o", "h", "l", "c", "dv", "npr", "hl2", "spread",
                 "dv_win", "sig_win", "day_med")

    def __init__(self, z):
        self.o = z["o"].astype(np.float64)
        self.h = z["h"].astype(np.float64)
        self.l = z["l"].astype(np.float64)
        self.c = z["c"].astype(np.float64)
        self.dv = z["dv"].astype(np.float64)
        self.npr = z["npr"].astype(np.int64)
        self.hl2 = z["hl2"].astype(np.float64)
        self.spread = None
        self.dv_win = None
        self.sig_win = None
        self.day_med = None


class CostModel:
    """Per-fill measured cost, with a disk cache of per-minute stats.

    `cost_bps(sym, date, t, notional, side=...)` returns bps for ONE
    side of the trade. Every window used ends strictly before `t`.
    """

    def __init__(self, floor_bps=FLOOR_BPS, legacy_bps=LEGACY_BPS,
                 impact_coef=IMPACT_COEF, ext_floor_bps=None,
                 enable_impact=True, prior_days=None,
                 spread_mode="max"):
        self.spread_mode = spread_mode
        self.floor = float(floor_bps)
        self.legacy = float(legacy_bps)
        self.coef = float(impact_coef)
        self.ext_floor = legacy_bps if ext_floor_bps is None \
            else float(ext_floor_bps)
        self.enable_impact = bool(enable_impact)
        self._days = {}
        self._prior = {}          # sym -> {date: day-median spread bps}
        self._dates = prior_days  # optional sym -> sorted date list
        self.tally = {}
        self.samples = []
        self.keep_samples = False

    # ---------- loading ----------
    def _day(self, sym, date):
        k = (sym, date)
        d = self._days.get(k, 0)
        if d != 0:
            return d
        f = cfile(sym, date)
        if not f.exists():
            # build on demand from the tape if it is there
            if (XDIR / f"{sym}_{date}.json.gz").exists():
                build_one(sym, date)
            if not f.exists():
                self._days[k] = None
                return None
        try:
            with np.load(f) as z:
                d = _Day(z)
        except Exception:
            d = None
        if d is not None:
            self._rolling(d)
        self._days[k] = d
        return d

    # ---------- the causal rolling estimates ----------
    def _rolling(self, d):
        """Fill d.spread[m] / d.dv_win[m] / d.sig_win[m] for every m,
        each from bars STRICTLY BEFORE m."""
        n = NMIN
        spread = np.full(n, np.nan)
        dvw = np.zeros(n)
        sigw = np.full(n, np.nan)
        # trailing dollar volume, strictly before m
        cdv = np.concatenate([[0.0], np.cumsum(d.dv)])
        for m in range(n):
            a = max(0, m - IMPACT_WIN)
            dvw[m] = cdv[m] - cdv[a]
        # 1-minute log returns off the minute closes that printed
        for m in range(n):
            a = max(0, m - IMPACT_WIN)
            cc = d.c[a:m]
            cc = cc[cc > 0]
            if len(cc) >= 3:
                r = np.diff(np.log(cc))
                if len(r) >= 2:
                    # scale to the horizon actually covered by the
                    # window (m - a minutes), not to a nominal 10 --
                    # at 09:35 the window is 5 minutes long and
                    # sqrt(10) would over-state sigma.
                    sigw[m] = float(np.std(r, ddof=1)) * math.sqrt(
                        max(1, m - a)) * 1e4
        # spread: max(HL2, CS, AR) on trailing windows.
        # CS/AR are cumulative-sum means over PER-PAIR arrays: pair i
        # spans bars i and i+1, so the window [b0, m) of BARS is the
        # window [b0, m-1) of PAIRS -- exactly what cs_bps/ar_bps loop
        # over, and --selftest asserts the two agree to 1e-9.
        cs_s, cs_ok = cs_pairs(d.o, d.h, d.l)
        ar_x, ar_ok = ar_pairs(d.h, d.l, d.c)
        cs_cs = np.concatenate([[0.0], np.cumsum(np.where(cs_ok, cs_s, 0.0))])
        cs_cn = np.concatenate([[0], np.cumsum(cs_ok.astype(np.int64))])
        ar_cs = np.concatenate([[0.0], np.cumsum(np.where(ar_ok, ar_x, 0.0))])
        ar_cn = np.concatenate([[0], np.cumsum(ar_ok.astype(np.int64))])
        npair = len(cs_s)
        for m in range(n):
            a = max(0, m - SPREAD_WIN)
            w = d.hl2[a:m]
            w = w[np.isfinite(w)]
            hl = float(np.median(w)) if len(w) >= MIN_MIN_HL2 else None
            if hl is None:
                a2 = max(0, m - WIDE_WIN)
                w = d.hl2[a2:m]
                w = w[np.isfinite(w)]
                hl = float(np.median(w)) if len(w) >= MIN_MIN_HL2 else None
            b0 = max(0, m - CSAR_WIN)
            pa, pb = min(b0, npair), min(max(m - 1, 0), npair)
            cs = _win_mean(cs_cs, cs_cn, pa, pb, MIN_PAIRS)
            cs = None if cs is None else 1e4 * cs
            arm = _win_mean(ar_cs, ar_cn, pa, pb, MIN_PAIRS)
            ar = None if arm is None else 1e4 * math.sqrt(
                max(4.0 * arm, 0.0))
            vals = [v for v in (hl, cs, ar) if v is not None]
            if vals:
                if self.spread_mode == "max":
                    spread[m] = max(vals)
                elif self.spread_mode == "med":
                    spread[m] = float(np.median(vals))
                elif self.spread_mode == "cs":
                    spread[m] = cs if cs is not None else max(vals)
                elif self.spread_mode == "hl2":
                    spread[m] = hl if hl is not None else max(vals)
                else:
                    raise ValueError(self.spread_mode)
        d.spread = spread
        d.dv_win = dvw
        d.sig_win = sigw
        ok = spread[np.isfinite(spread)]
        d.day_med = float(np.median(ok)) if len(ok) else None

    # ---------- prior-session fallback (strictly past) ----------
    def _prior_med(self, sym, date):
        """Day-median spread of the most recent EARLIER session of the
        same symbol that is in the cache. Strictly past information."""
        cache = self._prior.setdefault(sym, {})
        if date in cache:
            return cache[date]
        if "_dates" not in cache:
            cache["_dates"] = _index().get(sym, [])
        ds = cache["_dates"]
        i = bisect_left(ds, date)
        val = None
        for j in range(i - 1, max(-1, i - 6), -1):
            dd = self._day(sym, ds[j])
            if dd is not None and dd.day_med is not None:
                val = dd.day_med
                break
        cache[date] = val
        return val

    # ---------- the public lookup ----------
    def parts(self, sym, date, t, notional):
        """(half_spread_bps, impact_bps, tier) for a fill at minute t."""
        m = mkey(t)
        d = self._day(sym, date) if m >= 0 else None
        sp = None
        tier = "legacy"
        if d is not None:
            v = d.spread[m]
            if np.isfinite(v):
                sp, tier = float(v), "win"
        if sp is None:
            pv = self._prior_med(sym, date)
            if pv is not None:
                sp, tier = float(pv), "prior"
        if sp is None:
            sp, tier = self.legacy * 2.0, "legacy"
        half = max(self.floor, sp / 2.0)
        imp = 0.0
        if self.enable_impact and d is not None and m >= 0:
            dvw = d.dv_win[m]
            sg = d.sig_win[m]
            if dvw > 0 and np.isfinite(sg) and notional > 0:
                imp = self.coef * sg * math.sqrt(notional / dvw)
            elif notional > 0:
                imp = self.legacy       # no volume at all -> conservative
        return half, imp, tier

    def cost_bps(self, sym, date, t, notional, passive=False):
        """Per-side cost in bps.

        `passive=True` is a RESTING LIMIT that was filled by someone
        else crossing to it: you do not pay the half-spread, you earn
        it. What such a fill still costs is adverse selection plus the
        impact of the size you took, so the passive leg is charged the
        impact term alone (floored). This is the measured analogue of
        UNIVERSE-QUOTES' `passive_bps=0.0` convention, and it is
        strictly more expensive than theirs, never less."""
        half, imp, tier = self.parts(sym, date, t, notional)
        c = max(self.floor, (0.0 if passive else half) + imp)
        if not (RTH_LO <= t < RTH_HI):
            c = max(c, self.ext_floor)
            tier = tier + "+ext"
        self.tally[tier] = self.tally.get(tier, 0) + 1
        self.tally["_n"] = self.tally.get("_n", 0) + 1
        if c > LEGACY_BPS:
            self.tally["_gt10"] = self.tally.get("_gt10", 0) + 1
        self.tally["_sum"] = self.tally.get("_sum", 0.0) + c
        if self.keep_samples:
            self.samples.append(dict(sym=sym, date=date, t=str(t),
                                     half=half, imp=imp, tier=tier,
                                     bps=c, notional=notional))
        return c

    def report(self):
        n = self.tally.get("_n", 0)
        return dict(
            n=n,
            mean_bps=(self.tally.get("_sum", 0.0) / n) if n else None,
            frac_gt_10bps=(self.tally.get("_gt10", 0) / n) if n else None,
            tiers={k: v for k, v in sorted(self.tally.items())
                   if not k.startswith("_")})

    def reset(self):
        self.tally = {}
        self.samples = []


# ======================================================================
# build driver + self test
# ======================================================================

def _build_worker(args):
    sym, date = args
    try:
        return build_one(sym, date)
    except Exception as e:
        return f"err:{type(e).__name__}"


def cmd_build(pairs, workers=4):
    CDIR.mkdir(parents=True, exist_ok=True)
    todo = [(s, d) for s, d in pairs if not cfile(s, d).exists()]
    print(f"cost1 build: {len(pairs):,} pairs, {len(todo):,} to do",
          flush=True)
    t0 = time.monotonic()
    stats = {}
    if workers > 1:
        from concurrent.futures import ProcessPoolExecutor
        with ProcessPoolExecutor(max_workers=workers) as ex:
            for i, r in enumerate(ex.map(_build_worker, todo,
                                         chunksize=64), 1):
                stats[r] = stats.get(r, 0) + 1
                if i % 5000 == 0:
                    el = time.monotonic() - t0
                    print(f"  [{i:,}/{len(todo):,}] {stats} "
                          f"{i/el:.0f}/s eta {(len(todo)-i)/(i/el)/60:.0f}m",
                          flush=True)
    else:
        for i, p in enumerate(todo, 1):
            r = _build_worker(p)
            stats[r] = stats.get(r, 0) + 1
    print(f"DONE {(time.monotonic()-t0)/60:.1f}m {stats}", flush=True)
    return stats


def selftest():
    """Three proofs:
    (1) the vectorised CS / AR reproduce liquidity_estimators.py's
        reference implementations on real bars;
    (2) the rolling estimate at minute m does not move when every bar
        at or after m is destroyed (causality);
    (3) the model never returns 0 and never returns NaN.
    """
    import importlib.util
    import pandas as pd
    spec = importlib.util.spec_from_file_location(
        "le", HERE / "liquidity_estimators.py")
    le = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(le)

    syms = sorted(CDIR.glob("*.npz"))[:40]
    assert syms, "no cost1 cache built yet"
    nchk = nbad = 0
    worst = 0.0
    for f in syms:
        sym, date = f.name[:-4].split("_", 1)
        with np.load(f) as z:
            d = _Day(z)
        idx = pd.date_range(f"{date} 09:30", periods=NMIN, freq="1min")
        df = pd.DataFrame({"Open": d.o, "High": d.h, "Low": d.l,
                           "Close": d.c, "Volume": d.dv}, index=idx)
        for m in (60, 120, 200, 300):
            ts = idx[m]
            sub = df[(df.index < ts)]
            sub = sub[sub["Close"] > 0]      # reference drops nothing;
            # compare on the SAME 30-bar window the vectorised code uses
            a = cs_bps(d.o, d.h, d.l, max(0, m - CSAR_WIN), m)
            b = le.corwin_schultz(df, ts, lookback=CSAR_WIN)
            if a is not None and b is not None:
                nchk += 1
                e = abs(a - b * 100.0)
                worst = max(worst, e)
                if e > 1e-6:
                    nbad += 1
            a = ar_bps(d.h, d.l, d.c, max(0, m - CSAR_WIN), m)
            b = le.abdi_ranaldo(df, ts, lookback=CSAR_WIN)
            if a is not None and b is not None:
                nchk += 1
                e = abs(a - b * 100.0)
                worst = max(worst, e)
                if e > 1e-6:
                    nbad += 1
    print(f"[1] CS/AR vs liquidity_estimators.py: {nchk} checks, "
          f"{nbad} mismatches, worst {worst:.3e} bps")

    # [1b] the VECTORISED cumulative-sum form used by _rolling must equal
    # the scalar cs_bps / ar_bps above (which equal the reference).
    nv = nvb = 0
    wv = 0.0
    for f in syms[:20]:
        with np.load(f) as z:
            d = _Day(z)
        cs_s, cs_ok = cs_pairs(d.o, d.h, d.l)
        ar_x, ar_ok = ar_pairs(d.h, d.l, d.c)
        ccs = np.concatenate([[0.0], np.cumsum(np.where(cs_ok, cs_s, 0.0))])
        ccn = np.concatenate([[0], np.cumsum(cs_ok.astype(np.int64))])
        acs = np.concatenate([[0.0], np.cumsum(np.where(ar_ok, ar_x, 0.0))])
        acn = np.concatenate([[0], np.cumsum(ar_ok.astype(np.int64))])
        npair = len(cs_s)
        for m in range(31, NMIN, 7):
            b0 = max(0, m - CSAR_WIN)
            pa, pb = min(b0, npair), min(max(m - 1, 0), npair)
            v = _win_mean(ccs, ccn, pa, pb, MIN_PAIRS)
            v = None if v is None else 1e4 * v
            r = cs_bps(d.o, d.h, d.l, b0, m)
            if (v is None) != (r is None):
                nvb += 1
            elif v is not None:
                nv += 1
                wv = max(wv, abs(v - r))
                if abs(v - r) > 1e-9:
                    nvb += 1
            am = _win_mean(acs, acn, pa, pb, MIN_PAIRS)
            v2 = None if am is None else 1e4 * math.sqrt(max(4.0 * am, 0.0))
            r2 = ar_bps(d.h, d.l, d.c, b0, m)
            if (v2 is None) != (r2 is None):
                nvb += 1
            elif v2 is not None:
                nv += 1
                wv = max(wv, abs(v2 - r2))
                if abs(v2 - r2) > 1e-9:
                    nvb += 1
    print(f"[1b] vectorised vs scalar CS/AR: {nv} checks, {nvb} "
          f"mismatches, worst {wv:.3e} bps")

    # (2) causality
    cm = CostModel()
    nmove = ncau = 0
    for f in syms[:12]:
        sym, date = f.name[:-4].split("_", 1)
        with np.load(f) as z:
            d0 = _Day(z)
        cm._rolling(d0)
        for m in (45, 90, 180, 250):
            d1 = _Day({k: getattr(d0, k).astype(np.float32)
                       for k in ("o", "h", "l", "c", "dv", "hl2")}
                      | {"npr": d0.npr.astype(np.int32)})
            for k in ("o", "h", "l", "c", "dv", "hl2"):
                arr = getattr(d1, k)
                arr[m:] = (np.nan if k == "hl2" else 0.0)
            cm._rolling(d1)
            ncau += 1
            a0, a1 = d0.spread[m], d1.spread[m]
            b0, b1 = d0.dv_win[m], d1.dv_win[m]
            same = ((np.isnan(a0) and np.isnan(a1)) or a0 == a1) and b0 == b1
            if not same:
                nmove += 1
    print(f"[2] poison (tape destroyed at/after m): {ncau} checks, "
          f"{nmove} leaks")

    # (3) never zero / never NaN
    cm = CostModel()
    n = bad = 0
    for f in syms:
        sym, date = f.name[:-4].split("_", 1)
        for m in range(0, 390, 17):
            t = dtime((MIN_M + m) // 60, (MIN_M + m) % 60)
            c = cm.cost_bps(sym, date, t, 15000.0)
            n += 1
            if not (c > 0) or not np.isfinite(c):
                bad += 1
    print(f"[3] {n} lookups, {bad} non-positive/NaN, report="
          f"{json.dumps(cm.report())}")
    return nbad == 0 and nvb == 0 and nmove == 0 and bad == 0


def main():
    argv = sys.argv[1:]
    if "--selftest" in argv:
        ok = selftest()
        print("SELFTEST", "PASS" if ok else "FAIL")
        raise SystemExit(0 if ok else 1)
    if "--build" in argv:
        w = int(argv[argv.index("--workers") + 1]) if "--workers" in argv \
            else 4
        if "--pairs" in argv:
            pairs = json.loads(
                Path(argv[argv.index("--pairs") + 1]).read_text())
        else:
            pairs = [p.name[:-8].split("_", 1) for p in
                     XDIR.glob("*.json.gz")]
            pairs = [(a, b) for a, b in pairs]
        cmd_build([tuple(p) for p in pairs], w)
        return
    print(__doc__)


if __name__ == "__main__":
    main()
