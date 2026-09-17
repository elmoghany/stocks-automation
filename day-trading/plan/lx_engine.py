"""LIMIT-EXEC (2026-09-17) -- an END-TO-END limit execution engine on the
entitled 1-second tape: limit ENTRIES and limit EXITS, sized to the tape,
with causal cancel/replace ladders.

WHY. HARNESS-DIAGNOSTIC control 5 found the market-order / immediacy
assumption to be the single largest lever in the frame (+$3,190/month on
the measured half-spread), and its zero-information baseline is exactly
the toll: -$28.6 per $15,000 ticket at 10 bps a side, ~$0 at zero cost.
UNIVERSE-QUOTES modelled the ENTRY side only and found that a limit entry
is worth exactly the entry-side fee -- price improvement and adverse
selection cancel at every rung. COST-REBASE found that three wide-universe
rankers were partly selecting names the flat toll under-charged. This
module puts BOTH legs on the tape so the question "can execution alone
move the baseline from -$28 to ~$0" is answered with the exit included.

THE TAPE (plan/uq_sec1.py).  data/massive/trades/{SYM}_{DATE}.json.gz,
rows [t_ms, o, h, l, c, v, n] at 1-second resolution, 09:30-16:05 ET.
A second's `l` is the minimum TRADE price in that second, `h` the maximum,
`v` the shares traded.  /v3/quotes and /v3/trades are 403 on this account;
there is no NBBO, so "the bid" and "the ask" are the last print +/- a
CAUSAL half-spread estimate from plan/cr_cost.py (max of the HL2 / CS / AR
estimators over bars strictly before the posting minute).

THE FILL RULE, STATED BEFORE IT WAS TESTED (buy side; sell is mirrored)
  A buy limit at L posted at second t0 fills from 1-second bars with
  t > t0 (strictly after the post) whose low is <= L.
    * fill PRICE: L if the second opened above L (the price came down to a
      resting order), else min(L, open) -- the order was marketable on
      arrival and gets the market, never a worse price than its own limit
      (plan/uq_econ.fill_at, the convention that fixed UQ's one bug).
    * fill SIZE: a second with `v` shares traded at or below L can fill at
      most  part * v * share(L)  of our order, where share(L) is the
      fraction of the second's [l, h] range at or below L (1 if the whole
      second printed at or below L) and `part` is our assumed share of
      that volume (1.0 = everything that printed at our price was ours;
      0.5 = half of it was ahead of us in the queue).  Fills accumulate
      across seconds until the order is full or the rung expires.  This
      is the "volume in that second >= our size, else partial" rule of
      the mandate, made continuous.
    * `through` cents: require the low to reach L - through before a fill
      is believed (queue-position sensitivity, as UNIVERSE-QUOTES 3.2).
  The LADDER is a list of rungs (start_minute, limit) known at each
  rung's start from information <= that minute's boundary.  Modes:
    rest   post once at the anchor, wait N minutes
    tick   raise the limit by one tick per minute, anchored at the
           decision quote, until it reaches the estimated ask; then hold
    chase  re-anchor to the CURRENT bid (last print - half-spread at that
           minute boundary) every minute
  On timeout with shares still unfilled: `on_timeout` = "cancel" (keep
  whatever partial position filled; zero filled = no trade, the attempt
  is spent) or "market" (the remainder crosses at the open of the next
  printed minute, charged the MARKETABLE cost).
  EXIT: mirrored -- post at the ask at the exit decision minute, step
  DOWN one tick per minute for M minutes, then marketable; and always
  marketable at the hard flatten minute (the frame's 15:00 / the policy's
  stated exit bar), where the forced sale is at that bar's CLOSE exactly
  as plan/hd_foresight.py and plan/cm_lib.py price it.

COST CONVENTIONS, all three carried on every ticket so nothing has to be
re-run to read a different one:
    flat   passive legs 0 bps, marketable legs the incumbent 10 bps
           (+50 outside RTH) -- UNIVERSE-QUOTES' convention
    meas   passive legs pay measured IMPACT only, marketable legs pay
           measured half-spread + impact (plan/cr_cost.CostModel,
           Y = 1.0) -- COST-REBASE's convention
    zero   no cost at all (the gross path)
  and `mkt` -- the same ticket under MARKET fills on both sides at the
  flat 10 bps, i.e. the incumbent frame's own number, so every limit
  ticket carries its own market counterfactual for the decomposition.

ADVERSE SELECTION ACCOUNTING (per filled limit leg)
    ref      the market price the leg would have paid (buy: open of the
             minute after the decision; sell: open of the minute after
             the exit decision)
    pi_bps   price improvement vs ref (positive = we paid less / got more)
    mo_bps   markout: the mid (last print) 5 minutes after the fill
             relative to the fill price, signed so that NEGATIVE means
             the price kept moving against us after filling us
  "came to us then reverted" = mo_bps >= 0 ; "filled on the way down"
  (or up, for a sell) = mo_bps < 0.  The net of price improvement minus
  adverse selection per configuration is what UNIVERSE-QUOTES found to be
  ~0 on the entry side; here the exit side is measured too.
"""
import gzip
import json
import math
import os
from datetime import datetime, time as dtime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
import sys                                                    # noqa: E402
sys.path.insert(0, str(HERE))
import cr_cost                                                # noqa: E402

ET = ZoneInfo("America/New_York")
XDIR = ROOT / "data" / "massive" / "trades"
DAYS = HERE / "rl2" / "out" / "days"
FEAT = HERE / "rl2" / "out" / "feat"
OUT = HERE / "lx_out"

NMIN = 960                    # 04:00-based minute grid
BASE_MIN = 240
RTH_LO, RTH_HI = 330, 720     # 09:30, 16:00 on that grid
SEC0_MIN = 330                # tape second 0 == 09:30
NSEC = (16 * 60 + 5 - 9 * 60 - 30) * 60     # 23,700 seconds 09:30-16:05
FEE_BPS, EXT_BPS = 10.0, 50.0
TICKET, MIN_NOTIONAL = 15000.0, 500.0
TICK = 0.01
MARKOUT_MIN = 5


def cost_frac(minute, bps=FEE_BPS):
    ext = (minute < RTH_LO) or (minute >= RTH_HI)
    return (bps + (EXT_BPS if ext else 0.0)) / 1e4


def minute_time(m):
    mm = m + BASE_MIN
    return dtime(mm // 60, mm % 60)


# ------------------------------------------------------------------ tape
TAPE_CACHE = ROOT / "data" / "massive" / "lx_tape"     # per-day npz mirror


class Tape:
    """One symbol-day of 1-second bars: `sec` = seconds since 09:30,
    o/h/l/c/v aligned, ascending."""
    __slots__ = ("sec", "o", "h", "l", "c", "v")

    def __init__(self, sec, o, h, l, c, v):
        self.sec, self.o, self.h, self.l, self.c, self.v = sec, o, h, l, c, v

    def __len__(self):
        return int(self.sec.size)


def _parse_rows(rows, t0_0930_ms):
    a = np.asarray(rows, dtype=np.float64)          # None -> nan
    if a.ndim != 2 or a.shape[0] == 0:
        return None
    ok = np.isfinite(a[:, 1]) & np.isfinite(a[:, 2]) & np.isfinite(a[:, 3])
    a = a[ok]
    if a.shape[0] == 0:
        return None
    sec = ((a[:, 0] - t0_0930_ms) // 1000).astype(np.int32)
    c = np.where(np.isfinite(a[:, 4]), a[:, 4], a[:, 1])
    v = np.where(np.isfinite(a[:, 5]), a[:, 5], 0.0)
    return Tape(sec, a[:, 1].copy(), a[:, 2].copy(), a[:, 3].copy(), c, v)


def load_tape(sym, date, t0_0930_ms):
    f = XDIR / f"{sym}_{date}.json.gz"
    if not f.exists() or f.stat().st_size == 0:
        return None
    try:
        with gzip.open(f, "rt") as h:
            rows = json.load(h)["rows"]
    except Exception:
        return None
    if not rows:
        return None
    return _parse_rows(rows, t0_0930_ms)


def load_day_tapes(date, syms, t0_0930_ms, cache_tag=""):
    """{sym: Tape or None} for a whole day, through a per-day npz mirror
    of the json.gz cache (same numbers, one file, ~10x faster to read)."""
    f = TAPE_CACHE / f"{date}{cache_tag}.npz"
    out = {}
    if f.exists():
        try:
            z = np.load(f)
            have = set(str(s) for s in z["syms"])
            for s in syms:
                if s in have:
                    out[s] = Tape(z[s + "__sec"], z[s + "__o"], z[s + "__h"],
                                  z[s + "__l"], z[s + "__c"], z[s + "__v"])
                else:
                    out[s] = None
            return out
        except Exception:
            pass
    arrs = {}
    keep = []
    for s in syms:
        tp = load_tape(s, date, t0_0930_ms)
        out[s] = tp
        if tp is not None:
            keep.append(s)
            arrs[s + "__sec"] = tp.sec
            arrs[s + "__o"] = tp.o
            arrs[s + "__h"] = tp.h
            arrs[s + "__l"] = tp.l
            arrs[s + "__c"] = tp.c
            arrs[s + "__v"] = tp.v.astype(np.float32)
    try:
        TAPE_CACHE.mkdir(parents=True, exist_ok=True)
        tmp = TAPE_CACHE / f"{date}{cache_tag}.{np.random.randint(1 << 30)}.part"
        np.savez(tmp, syms=np.array(keep), **arrs)
        tmp.replace(f)
    except Exception:
        pass
    return out


# ------------------------------------------------------------ fast cost
class FastCost:
    """plan/cr_cost.CostModel's `parts()` for ONE posting minute, computed
    from the same per-minute statistics (data/massive/cost1) with the
    same estimators (cr_cost.cs_bps / ar_bps, the scalar reference forms
    that cr_cost --selftest proves equal to the cumulative ones).

    Identical to CostModel.parts for tier "win" (asserted in
    plan/lx_poison.py --stage cost).  The PRIOR-session fallback -- used
    only when no trailing window exists yet, i.e. posts in the first
    minutes of the session -- is the prior day's max(median HL2, whole-day
    CS, whole-day AR) instead of CostModel's median of per-minute maxima:
    cheaper by two orders of magnitude, same ingredients, stated here.
    """

    def __init__(self, coef=cr_cost.IMPACT_COEF):
        self.coef = float(coef)
        self._d = {}
        self._idx = None

    def index(self):
        if self._idx is None:
            d = {}
            with os.scandir(cr_cost.CDIR) as it:
                for e in it:
                    n = e.name
                    if n.endswith(".npz") and "_" in n:
                        s, dt = n[:-4].split("_", 1)
                        d.setdefault(s, []).append(dt)
            for v in d.values():
                v.sort()
            self._idx = d
        return self._idx

    def day(self, sym, date):
        k = (sym, date)
        if k in self._d:
            return self._d[k]
        f = cr_cost.cfile(sym, date)
        d = None
        if not f.exists() and (XDIR / f"{sym}_{date}.json.gz").exists():
            try:
                cr_cost.build_one(sym, date)
            except Exception:
                pass
        if f.exists():
            try:
                with np.load(f) as z:
                    d = {kk: z[kk].astype(np.float64) for kk in
                         ("o", "h", "l", "c", "dv", "hl2")}
            except Exception:
                d = None
        if len(self._d) > 4000:
            self._d.clear()
        self._d[k] = d
        return d

    @staticmethod
    def _spread_at(d, k):
        hl2 = d["hl2"]
        w = hl2[max(0, k - cr_cost.SPREAD_WIN):k]
        w = w[np.isfinite(w)]
        hl = float(np.median(w)) if len(w) >= cr_cost.MIN_MIN_HL2 else None
        if hl is None:
            w = hl2[max(0, k - cr_cost.WIDE_WIN):k]
            w = w[np.isfinite(w)]
            hl = float(np.median(w)) if len(w) >= cr_cost.MIN_MIN_HL2 else None
        b0 = max(0, k - cr_cost.CSAR_WIN)
        cs = cr_cost.cs_bps(d["o"], d["h"], d["l"], b0, k)
        ar = cr_cost.ar_bps(d["h"], d["l"], d["c"], b0, k)
        vals = [v for v in (hl, cs, ar) if v is not None]
        return max(vals) if vals else None

    def _prior(self, sym, date):
        ds = self.index().get(sym, [])
        from bisect import bisect_left
        i = bisect_left(ds, date)
        for j in range(i - 1, max(-1, i - 6), -1):
            d = self.day(sym, ds[j])
            if d is None:
                continue
            w = d["hl2"][np.isfinite(d["hl2"])]
            hl = float(np.median(w)) if len(w) >= cr_cost.MIN_MIN_HL2 else None
            n = len(d["o"])
            cs = cr_cost.cs_bps(d["o"], d["h"], d["l"], 0, n)
            ar = cr_cost.ar_bps(d["h"], d["l"], d["c"], 0, n)
            vals = [v for v in (hl, cs, ar) if v is not None]
            if vals:
                return max(vals)
        return None

    def parts(self, sym, date, m_post, notional):
        """(half_spread_bps, impact_bps, tier) for an order posted at the
        start of minute m_post (04:00-based grid); windows end strictly
        before it."""
        k = m_post - SEC0_MIN                    # cost1 index: 0 == 09:30
        d = self.day(sym, date) if 0 <= k < cr_cost.NMIN else None
        sp, tier = None, "legacy"
        if d is not None:
            sp = self._spread_at(d, k)
            if sp is not None:
                tier = "win"
        if sp is None:
            pv = self._prior(sym, date)
            if pv is not None:
                sp, tier = pv, "prior"
        if sp is None:
            sp = cr_cost.LEGACY_BPS * 2.0
        half = max(cr_cost.FLOOR_BPS, sp / 2.0)
        imp = 0.0
        if d is not None and notional > 0:
            a = max(0, k - cr_cost.IMPACT_WIN)
            dvw = float(d["dv"][a:k].sum())
            cc = d["c"][a:k]
            cc = cc[cc > 0]
            sg = np.nan
            if len(cc) >= 3:
                r = np.diff(np.log(cc))
                if len(r) >= 2:
                    sg = float(np.std(r, ddof=1)) * math.sqrt(max(1, k - a)) * 1e4
            if dvw > 0 and np.isfinite(sg):
                imp = self.coef * sg * math.sqrt(notional / dvw)
            else:
                imp = cr_cost.LEGACY_BPS
        elif notional > 0:
            imp = cr_cost.LEGACY_BPS
        return half, imp, tier


# ------------------------------------------------------------------- day
class Day:
    """Minute grid (rl2 causal wide panel) + lazily loaded tapes + the
    measured cost model for one date."""

    def __init__(self, date, syms=None, cost_model=None, panel=None,
                 cache_tag=""):
        self.date = date
        if panel is None:
            z = np.load(DAYS / f"{date}.npz", allow_pickle=False)
            self.syms = [str(s) for s in z["syms"]]
            self.o = z["o"].astype(np.float64)
            self.h = z["h"].astype(np.float64)
            self.l = z["l"].astype(np.float64)
            self.c = z["c"].astype(np.float64)
            self.v = z["v"].astype(np.float64)
        else:
            self.syms, self.o, self.h, self.l, self.c, self.v = panel
        self.sidx = {s: i for i, s in enumerate(self.syms)}
        self.printed = ~np.isnan(self.c)
        self.cf = _ffill(self.c)                     # last print <= m
        self.cvol = np.cumsum(np.nan_to_num(self.v), axis=1)
        y, mo, d = (int(x) for x in date.split("-"))
        self.t0_0930 = int(datetime(y, mo, d, 9, 30, tzinfo=ET)
                           .timestamp()) * 1000
        # next printed minute >= k
        S = len(self.syms)
        nxt = np.full((S, NMIN + 1), NMIN, np.int32)
        for k in range(NMIN - 1, -1, -1):
            nxt[:, k] = np.where(self.printed[:, k], k, nxt[:, k + 1])
        self.nxt = nxt[:, :NMIN]
        any_p = self.printed.any(axis=1)
        last = np.where(any_p, NMIN - 1 - np.argmax(self.printed[:, ::-1],
                                                   axis=1), -1)
        self.flat_min = last.astype(np.int32)
        self._tape = load_day_tapes(date, self.syms, self.t0_0930, cache_tag)
        # CONSISTENCY GUARD: the tape (adjusted 1-second bars) and the
        # minute grid must describe the same price.  A symbol-day whose
        # tape prints sit outside its own minute bar's [low, high] (a
        # split-adjustment disagreement between two caches) is DROPPED
        # from the tape, never priced.  Counted in `n_tape_dropped`.
        self.n_tape_dropped = 0
        for s, tp in list(self._tape.items()):
            if tp is None:
                continue
            si = self.sidx[s]
            bad = False
            checked = 0
            for k in (335, 340, 360, 400, 500):
                if not self.printed[si, k]:
                    continue
                a = (k - SEC0_MIN) * 60
                w = tp.c[(tp.sec >= a) & (tp.sec < a + 60)]
                if w.size == 0:
                    continue
                med = float(np.median(w))
                lo, hi = float(self.l[si, k]), float(self.h[si, k])
                checked += 1
                if not (lo * 0.97 <= med <= hi * 1.03):
                    bad = True
                if checked >= 2:
                    break
            if bad:
                self._tape[s] = None
                self.n_tape_dropped += 1
        self.cm = cost_model if cost_model is not None else FastCost()

    # ---- tape
    def tape(self, si):
        return self._tape.get(self.syms[si])

    def has_tape(self, si):
        return self.tape(si) is not None

    # ---- causal quantities at minute m (bars <= m)
    def mark(self, si, m):
        return float(self.cf[si, m])

    def volcap_shares(self, si, m, win=5, frac=0.20):
        lo = max(m - win, 0)
        return frac * float(self.cvol[si, m] - self.cvol[si, lo])

    def half_spread_bps(self, si, m_post, notional):
        """(half_spread_bps, impact_bps, tier) from bars strictly before
        minute m_post (the minute the order is posted at the start of)."""
        try:
            half, imp, tier = self.cm.parts(self.syms[si], self.date, m_post,
                                            notional)
        except Exception:
            half, imp, tier = cr_cost.LEGACY_BPS, cr_cost.LEGACY_BPS, "legacy"
        return float(half), float(imp), tier

    def mid_at_sec(self, si, s):
        """Last print at or before second s (the tape's own mark)."""
        tp = self.tape(si)
        if tp is None:
            return np.nan
        i = int(np.searchsorted(tp.sec, s, side="right")) - 1
        return float(tp.c[i]) if i >= 0 else np.nan

    def next_open(self, si, m):
        """(price, minute) of the first printed minute >= m, or (nan, -1)."""
        k = int(self.nxt[si, min(m, NMIN - 1)])
        if k >= NMIN:
            return np.nan, -1
        return float(self.o[si, k]), k


def _ffill(a):
    idx_ = np.where(~np.isnan(a), np.arange(a.shape[1])[None, :], 0)
    np.maximum.accumulate(idx_, axis=1, out=idx_)
    out = a[np.arange(a.shape[0])[:, None], idx_]
    first = np.argmax(~np.isnan(a), axis=1)
    never = np.isnan(a).all(axis=1)
    for i in range(a.shape[0]):
        if never[i]:
            out[i] = np.nan
        else:
            out[i, :first[i]] = np.nan
    return out


# --------------------------------------------------------------- ladders
def _rungs(mode, side, anchor_px, half_px, m_post, wait, day=None, si=None,
           n_min_tick=1):
    """List of (minute, limit) rungs for a ladder posted at the start of
    minute m_post.  side +1 buy / -1 sell.  `anchor_px` is the last print
    at the decision, `half_px` the estimated half-spread in dollars.

    rest : one rung at bid (buy) / ask (sell) for `wait` minutes
    tick : one rung per minute, moving one tick toward the far quote
           until it reaches it, then holding there
    chase: one rung per minute, re-anchored at that minute's own last
           print +/- the same half-spread (causal: the print is <= the
           boundary)
    mid  : rest at the last print itself (k = 0 of UNIVERSE-QUOTES)
    """
    if mode == "mid":
        return [(m_post, anchor_px)]
    near = anchor_px - side * half_px            # bid for a buy, ask for a sell
    far = anchor_px + side * half_px
    if mode == "rest":
        return [(m_post, near)]
    if mode == "tick":
        out, L = [], near
        for j in range(wait):
            out.append((m_post + j, L))
            L = L + side * TICK * n_min_tick
            if side > 0:
                L = min(L, far)
            else:
                L = max(L, far)
        return out
    if mode == "chase":
        out = []
        for j in range(wait):
            m = m_post + j
            mk = day.mark(si, m - 1) if m - 1 >= 0 else anchor_px
            if not np.isfinite(mk) or mk <= 0:
                mk = anchor_px
            out.append((m, mk - side * half_px))
        return out
    raise ValueError(mode)


def _fill_scan(tp, side, s_lo, s_hi, L, shares, part, through, range_share):
    """Walk seconds in [s_lo, s_hi) for a `side` limit at L.
    Returns (filled_shares, fill_dollars, first_sec, last_sec)."""
    a = int(np.searchsorted(tp.sec, s_lo, side="left"))
    b = int(np.searchsorted(tp.sec, s_hi, side="left"))
    if b <= a:
        return 0.0, 0.0, -1, -1
    o, h, l, v = tp.o[a:b], tp.h[a:b], tp.l[a:b], tp.v[a:b]
    if side > 0:
        hit = l <= L - through
    else:
        hit = h >= L + through
    if not hit.any():
        return 0.0, 0.0, -1, -1
    idx = np.flatnonzero(hit)
    o, h, l, v = o[idx], h[idx], l[idx], v[idx]
    rng = np.maximum(h - l, 1e-12)
    if range_share:
        if side > 0:
            sh = np.where(h <= L, 1.0, np.clip((L - l) / rng, 0.0, 1.0))
        else:
            sh = np.where(l >= L, 1.0, np.clip((h - L) / rng, 0.0, 1.0))
    else:
        sh = np.ones(idx.size)
    avail = part * v * sh
    if side > 0:
        px = np.where(o > L, L, np.minimum(L, o))
    else:
        px = np.where(o < L, L, np.maximum(L, o))
    filled = 0.0
    dollars = 0.0
    first = last = -1
    remaining = shares
    for k in range(idx.size):
        if remaining <= 1e-9:
            break
        q = min(remaining, float(avail[k]))
        if q <= 0:
            continue                 # a second with no volume fills nothing
        filled += q
        dollars += q * float(px[k])
        remaining -= q
        if first < 0:
            first = int(tp.sec[a + idx[k]])
        last = int(tp.sec[a + idx[k]])
    return filled, dollars, first, last


def execute_leg(day, si, side, m_dec, shares, spec, hard_flat=None):
    """Run one ladder for `shares` of symbol si.

    side   +1 buy, -1 sell
    m_dec  the decision minute (information <= m_dec); the first rung is
           posted at the start of minute m_dec + 1
    spec   dict: mode, wait, on_timeout ('cancel'|'market'), part,
           through, range_share, k_bps (extra offset beyond the quote,
           positive = more passive)
    hard_flat  (sell only) minute at whose CLOSE any remainder is sold
    Returns dict: filled, px (vwap of filled shares), mkt_px (remainder
    crossed at this price), mkt_shares, first_sec, last_sec, rungs,
    half_bps, imp_bps, tier, m_fill (minute of first fill), m_done.
    """
    tp = day.tape(si)
    m_post = m_dec + 1
    out = {"filled": 0.0, "px": np.nan, "mkt_px": np.nan, "mkt_shares": 0.0,
           "first_sec": -1, "last_sec": -1, "m_fill": -1, "m_done": -1,
           "half_bps": np.nan, "imp_bps": np.nan, "tier": "none",
           "passive_shares": 0.0, "ref_px": np.nan, "ref_m": -1}
    ref_px, ref_m = day.next_open(si, m_post)
    out["ref_px"], out["ref_m"] = ref_px, ref_m
    if tp is None or m_post >= NMIN:
        return out
    anchor = day.mark(si, m_dec)
    if not np.isfinite(anchor) or anchor <= 0:
        return out
    notional = shares * anchor
    half_bps, imp_bps, tier = day.half_spread_bps(si, m_post, notional)
    out.update(half_bps=half_bps, imp_bps=imp_bps, tier=tier)
    half_px = anchor * (half_bps / 1e4)
    k_px = anchor * (spec.get("k_bps", 0.0) / 1e4)
    wait = int(spec.get("wait", 1))
    mode = spec.get("mode", "rest")
    rungs = _rungs(mode, side, anchor, half_px, m_post, wait, day, si)
    # extra passivity beyond the quote; limits live on a 4-decimal grid
    rungs = [(m, round(L - side * k_px, 4)) for m, L in rungs]
    # the ladder cannot run past the hard flatten minute
    m_end = m_post + wait
    if hard_flat is not None:
        m_end = min(m_end, hard_flat)
    remaining = shares
    dollars = 0.0
    filled = 0.0
    first = last = -1
    part = float(spec.get("part", 1.0))
    through = float(spec.get("through", 0.0))
    rs = bool(spec.get("range_share", True))
    for j, (m, L) in enumerate(rungs):
        if m >= m_end or remaining <= 1e-9:
            break
        m_next = rungs[j + 1][0] if j + 1 < len(rungs) else m_end
        m_next = min(m_next, m_end)
        # posted at the START of minute m: only seconds STRICTLY after the
        # post second may fill it (the post second's own bar aggregates
        # trades that happened before the order existed)
        s_lo = (m - SEC0_MIN) * 60 + 1
        s_hi = (m_next - SEC0_MIN) * 60 + 1
        if s_hi <= s_lo:
            continue
        q, dq, f1, f2 = _fill_scan(tp, side, s_lo, s_hi, L, remaining, part,
                                   through, rs)
        if q > 0:
            filled += q
            dollars += dq
            remaining -= q
            if first < 0:
                first = f1
                out["m_fill"] = SEC0_MIN + f1 // 60
            last = f2
    out["passive_shares"] = filled
    out["rungs"] = len(rungs)
    used = [L for m, L in rungs if m < m_end]
    out["lim_hi"] = float(max(used)) if used else np.nan
    out["lim_lo"] = float(min(used)) if used else np.nan
    if remaining > 1e-9 and spec.get("on_timeout", "cancel") == "market":
        # cross at the open of the first printed minute >= m_end
        if hard_flat is not None and m_end >= hard_flat:
            px = float(day.cf[si, hard_flat]) if hard_flat < NMIN else np.nan
            mm = hard_flat
        else:
            px, mm = day.next_open(si, m_end)
        if np.isfinite(px) and px > 0:
            out["mkt_px"] = px
            out["mkt_shares"] = remaining
            filled += remaining
            dollars += remaining * px
            if first < 0:
                out["m_fill"] = mm
            out["m_done"] = mm
            remaining = 0.0
    if filled > 0:
        out["filled"] = filled
        out["px"] = dollars / filled
        out["first_sec"], out["last_sec"] = first, last
        if out["m_done"] < 0:
            out["m_done"] = SEC0_MIN + last // 60 if last >= 0 else m_end
    return out


def _market_exit(day, si, m_from, hold, flat_m, exit_dec, exit_conv):
    """(price, minute) of the incumbent MARKET exit for a position opened
    at minute m_from."""
    if exit_dec is not None:
        return float(day.cf[si, flat_m]), int(flat_m)
    want = min(m_from + hold, flat_m)
    if exit_conv == "open_next":
        xm = int(day.nxt[si, want])
        if xm >= NMIN or xm > flat_m:
            return float(day.cf[si, flat_m]), int(flat_m)
        return float(day.o[si, xm]), xm
    return float(day.cf[si, want]), int(want)


def markout(day, si, sec, px, side, minutes=MARKOUT_MIN):
    """bps of (mid after `minutes` - px) signed so negative = adverse."""
    if sec < 0 or not np.isfinite(px) or px <= 0:
        return np.nan
    mid = day.mid_at_sec(si, sec + minutes * 60)
    if not np.isfinite(mid):
        return np.nan
    return side * (mid / px - 1.0) * 1e4


# ------------------------------------------------------------ the ticket
def ticket(day, si, m_dec, hold, entry, exit_, flat_m, ticket_usd=TICKET,
           volcap=True, cap_shares=None, exit_dec=None, exit_conv="close"):
    """One end-to-end limit ticket.

    m_dec     decision minute (info <= m_dec); the entry ladder posts at
              m_dec + 1
    hold      minutes from the FIRST fill to the exit decision
    exit_dec  if given, a fixed exit decision minute instead (policies
              with a stated exit bar, e.g. REV 15:30 -> 15:59)
    flat_m    hard flatten minute: any remainder is sold at its CLOSE
    entry/exit_ ladder specs; entry None = market at the open of m_dec+1
              (the incumbent fill); exit_ None = market at the close of
              the exit bar (the incumbent exit)
    Returns None when no position was taken (attempt spent, $0), else a
    dict with pnl under every cost convention and the decomposition.
    """
    if m_dec + 1 >= NMIN or flat_m <= m_dec + 1:
        return None
    mark = day.mark(si, m_dec)
    if not np.isfinite(mark) or mark <= 0:
        return None
    ref_px, ref_m = day.next_open(si, m_dec + 1)
    if cap_shares is None:
        cap_shares = day.volcap_shares(si, m_dec) if volcap else np.inf
    # size on information <= m_dec: shares = min(ticket/mark, cap)
    shares = ticket_usd / mark
    if np.isfinite(cap_shares) and cap_shares > 0:
        shares = min(shares, cap_shares)
    elif np.isfinite(cap_shares) and cap_shares <= 0 and volcap:
        return None
    if shares * mark < MIN_NOTIONAL:
        return None
    rec = {"sym": day.syms[si], "date": day.date, "m_dec": int(m_dec),
           "shares_want": float(shares)}
    # ---------------- entry
    if entry is None:
        if ref_m < 0 or ref_m > flat_m - 1 or not np.isfinite(ref_px):
            return None
        # the incumbent MARKET ticket sizes on the fill open itself
        # (plan/hd_foresight, plan/wn_table, plan/uq_strat -- non-causal,
        # reproduced here so their rows are recovered to the cent); the
        # LIMIT ticket above sizes on mark(m_dec), which is causal
        shares = ticket_usd / ref_px
        if np.isfinite(cap_shares) and cap_shares > 0:
            shares = min(shares, cap_shares)
        if shares * ref_px < MIN_NOTIONAL:
            return None
        e = {"filled": shares, "px": ref_px, "mkt_px": ref_px,
             "mkt_shares": shares, "passive_shares": 0.0, "m_fill": ref_m,
             "m_done": ref_m, "first_sec": (ref_m - SEC0_MIN) * 60,
             "last_sec": (ref_m - SEC0_MIN) * 60, "half_bps": np.nan,
             "imp_bps": np.nan, "tier": "market", "ref_px": ref_px,
             "ref_m": ref_m}
    else:
        e = execute_leg(day, si, +1, m_dec, shares, entry,
                        hard_flat=flat_m)
        if e["filled"] <= 0 or e["m_fill"] < 0 or e["m_fill"] >= flat_m:
            return None
        if e["filled"] * e["px"] < MIN_NOTIONAL and e["filled"] < shares:
            # a dust partial: cancelled remainder, position too small
            return None
    sh = e["filled"]
    rec["entry"] = e
    rec["shares"] = float(sh)
    rec["notional"] = float(sh * e["px"])
    # ---------------- exit decision
    if exit_dec is None:
        x_dec = e["m_fill"] + hold
    else:
        x_dec = exit_dec
    x_dec = min(x_dec, flat_m - 1)
    if x_dec <= e["m_done"] and exit_ is not None:
        # the ladder finished after the exit decision would have fired:
        # decide at the completion minute instead (still causal)
        x_dec = min(e["m_done"], flat_m - 1)
    x_dec = max(x_dec, e["m_fill"])
    rec["x_dec"] = int(x_dec)
    if exit_ is None:
        # incumbent market exit: "close" = the CLOSE of bar fill+hold
        # (plan/hd_foresight, plan/cm_lib); "open_next" = the OPEN of the
        # first printed minute at or after fill+hold, else the flatten
        # price (plan/rl2/features._targets, plan/uq_fills.exit_leg)
        px, xm = _market_exit(day, si, e["m_fill"], hold, flat_m, exit_dec,
                              exit_conv)
        if not np.isfinite(px) or px <= 0:
            return None
        x = {"filled": sh, "px": px, "mkt_px": px, "mkt_shares": sh,
             "passive_shares": 0.0, "m_fill": xm, "m_done": xm,
             "first_sec": (xm - SEC0_MIN) * 60, "last_sec": (xm - SEC0_MIN) * 60,
             "half_bps": np.nan, "imp_bps": np.nan, "tier": "market",
             "ref_px": px, "ref_m": xm}
    else:
        spec = dict(exit_, on_timeout="market")
        x = execute_leg(day, si, -1, x_dec, sh, spec, hard_flat=flat_m)
        if x["filled"] < sh - 1e-6:
            # could not even cross (no print to the flatten): sell the
            # remainder at the flatten close
            px = float(day.cf[si, flat_m])
            if not np.isfinite(px) or px <= 0:
                return None
            rem = sh - x["filled"]
            tot = x["filled"] * (x["px"] if np.isfinite(x["px"]) else 0.0)
            x["mkt_px"] = px
            x["mkt_shares"] += rem
            x["filled"] = sh
            x["px"] = (tot + rem * px) / sh
            if x["m_fill"] < 0:
                x["m_fill"] = flat_m
            x["m_done"] = flat_m
    rec["exit"] = x
    # ---------------- costs (entry / exit), per convention
    m_e, m_x = e["m_fill"], x["m_done"]
    pe, px_ = e["px"], x["px"]
    pas_e = e["passive_shares"] / sh if sh > 0 else 0.0
    pas_x = x["passive_shares"] / sh if sh > 0 else 0.0
    # flat: marketable share pays 10 bps (+50 ext), passive share 0
    ce_flat = (1 - pas_e) * cost_frac(m_e)
    cx_flat = (1 - pas_x) * cost_frac(m_x)
    # measured: passive pays impact only, marketable pays half + impact
    he, ie = e["half_bps"], e["imp_bps"]
    if not np.isfinite(he):
        he, ie, _t = day.half_spread_bps(si, m_e, sh * pe)
    hx, ix = x["half_bps"], x["imp_bps"]
    if not np.isfinite(hx):
        hx, ix, _t = day.half_spread_bps(si, m_x, sh * px_)
    ce_meas = max(cr_cost.FLOOR_BPS, ie + (1 - pas_e) * he) / 1e4
    cx_meas = max(cr_cost.FLOOR_BPS, ix + (1 - pas_x) * hx) / 1e4
    if m_e < RTH_LO or m_e >= RTH_HI:
        ce_meas = max(ce_meas, cost_frac(m_e))
    if m_x < RTH_LO or m_x >= RTH_HI:
        cx_meas = max(cx_meas, cost_frac(m_x))
    gross = sh * (px_ - pe)
    rec["pnl"] = {
        "zero": float(gross),
        "flat": float(sh * (px_ * (1 - cx_flat) - pe * (1 + ce_flat))),
        "meas": float(sh * (px_ * (1 - cx_meas) - pe * (1 + ce_meas))),
        "flat_all": float(sh * (px_ * (1 - cost_frac(m_x))
                                - pe * (1 + cost_frac(m_e)))),
    }
    rec["cost_bps"] = {"e_flat": ce_flat * 1e4, "x_flat": cx_flat * 1e4,
                       "e_meas": ce_meas * 1e4, "x_meas": cx_meas * 1e4}
    # ---------------- the market counterfactual on the SAME name/decision
    mkt = None
    if ref_m >= 0 and ref_m < flat_m and np.isfinite(ref_px) and ref_px > 0:
        pxo, xm = _market_exit(day, si, ref_m, hold, flat_m, exit_dec,
                               exit_conv)
        if np.isfinite(pxo) and pxo > 0:
            shm = min(ticket_usd / ref_px, cap_shares) if np.isfinite(cap_shares) \
                else ticket_usd / ref_px
            mkt = {"pnl_flat": float(shm * (pxo * (1 - cost_frac(xm))
                                            - ref_px * (1 + cost_frac(ref_m)))),
                   "pnl_zero": float(shm * (pxo - ref_px)),
                   "px_in": ref_px, "px_out": pxo, "m_in": int(ref_m),
                   "m_out": int(xm)}
    rec["mkt"] = mkt
    # ---------------- adverse-selection bookkeeping
    dec = {}
    if entry is not None and e["passive_shares"] > 0:
        dec["e_pi_bps"] = (ref_px / pe - 1.0) * 1e4 if np.isfinite(ref_px) else np.nan
        dec["e_mo_bps"] = markout(day, si, e["first_sec"], pe, +1)
        dec["e_wait_s"] = e["first_sec"] - (m_dec + 1 - SEC0_MIN) * 60
        dec["e_partial"] = float(e["passive_shares"] < sh - 1e-6)
    if exit_ is not None and x["passive_shares"] > 0:
        xref, xref_m = x["ref_px"], x["ref_m"]
        dec["x_pi_bps"] = (px_ / xref - 1.0) * 1e4 if np.isfinite(xref) and xref > 0 else np.nan
        dec["x_mo_bps"] = markout(day, si, x["first_sec"], px_, -1)
        dec["x_wait_s"] = x["first_sec"] - (x_dec + 1 - SEC0_MIN) * 60
        dec["x_partial"] = float(x["passive_shares"] < sh - 1e-6)
    rec["dec"] = dec
    rec["m_in"], rec["m_out"] = int(m_e), int(m_x)
    rec["px_in"], rec["px_out"] = float(pe), float(px_)
    rec["e_passive_frac"], rec["x_passive_frac"] = float(pas_e), float(pas_x)
    return rec


# ------------------------------------------------------------ reporting
def summarize(recs, ndays, key="flat", label=""):
    p = np.array([r["pnl"][key] for r in recs], float) if recs else np.zeros(0)
    ds = [r["date"] for r in recs]
    if p.size == 0:
        return {"label": label, "tickets": 0, "per_ticket": 0.0,
                "per_month": 0.0, "months_pos": "0/0", "ex_best": 0.0,
                "max_dd": 0.0, "tickets_per_day": 0.0, "days": ndays}
    by = {}
    for d, x in zip(ds, p):
        by[d] = by.get(d, 0.0) + x
    ser = np.array([by[d] for d in sorted(by)])
    eq = np.cumsum(ser)
    mon = {}
    for d, x in by.items():
        mon[d[:7]] = mon.get(d[:7], 0.0) + x
    mv = np.array([mon[m] for m in sorted(mon)])
    nmon = max(ndays / 21.0, 1e-9)
    aug = [r["pnl"][key] for r in recs if r["date"] >= "2026-08-01"]
    return {"label": label, "tickets": int(p.size),
            "tickets_per_day": round(p.size / max(ndays, 1), 3),
            "per_ticket": round(float(p.mean()), 2),
            "per_month": round(float(p.sum()) / nmon, 1),
            "total": round(float(p.sum()), 2),
            "months_pos": f"{int((mv > 0).sum())}/{len(mv)}",
            "ex_best": round(float(p.sum() - p.max()), 2),
            "max_dd": round(float(np.min(eq - np.maximum.accumulate(eq))), 2),
            "win_rate": round(float((p > 0).mean()), 4),
            "aug2026": {"tickets": len(aug),
                        "total": round(float(np.sum(aug)), 2) if aug else 0.0},
            "days": ndays, "y1": _yr(recs, key, lambda d: d < "2025-08-01"),
            "y2": _yr(recs, key, lambda d: "2025-08-01" <= d < "2026-08-01")}


def _yr(recs, key, f):
    p = [r["pnl"][key] for r in recs if f(r["date"])]
    return {"tickets": len(p), "per_ticket": round(float(np.mean(p)), 2) if p else 0.0}


def decomposition(recs):
    """Adverse-selection split for the passive legs of `recs`."""
    out = {}
    for leg in ("e", "x"):
        pi = np.array([r["dec"].get(f"{leg}_pi_bps", np.nan) for r in recs], float)
        mo = np.array([r["dec"].get(f"{leg}_mo_bps", np.nan) for r in recs], float)
        ok = np.isfinite(pi) & np.isfinite(mo)
        if ok.sum() == 0:
            out[leg] = {"n": 0}
            continue
        pi, mo = pi[ok], mo[ok]
        rev = mo >= 0
        out[leg] = {
            "n": int(ok.sum()),
            "pi_bps_mean": round(float(pi.mean()), 2),
            "markout5_bps_mean": round(float(mo.mean()), 2),
            "net_bps": round(float((pi + mo).mean()), 2),
            "share_reverted": round(float(rev.mean()), 4),
            "reverted": {"pi": round(float(pi[rev].mean()), 2) if rev.any() else None,
                         "mo": round(float(mo[rev].mean()), 2) if rev.any() else None},
            "way_down": {"pi": round(float(pi[~rev].mean()), 2) if (~rev).any() else None,
                         "mo": round(float(mo[~rev].mean()), 2) if (~rev).any() else None},
            "partial_share": round(float(np.mean(
                [r["dec"].get(f"{leg}_partial", 0.0) for r in recs
                 if f"{leg}_partial" in r["dec"]])), 4),
            "wait_s_median": round(float(np.median(
                [r["dec"][f"{leg}_wait_s"] for r in recs
                 if f"{leg}_wait_s" in r["dec"]])), 1)}
    return out


def fill_stats(recs, attempts):
    n = len(recs)
    if n == 0:
        return {"attempts": attempts, "fill_rate": 0.0}
    ep = np.array([r["e_passive_frac"] for r in recs])
    xp = np.array([r["x_passive_frac"] for r in recs])
    return {"attempts": attempts, "positions": n,
            "fill_rate": round(n / max(attempts, 1), 4),
            "entry_passive_frac_mean": round(float(ep.mean()), 4),
            "entry_fully_passive": round(float((ep > 0.999).mean()), 4),
            "exit_passive_frac_mean": round(float(xp.mean()), 4),
            "exit_fully_passive": round(float((xp > 0.999).mean()), 4),
            "mean_notional": round(float(np.mean([r["notional"] for r in recs])), 1),
            "cost_bps_mean": {k: round(float(np.mean([r["cost_bps"][k] for r in recs])), 2)
                              for k in ("e_flat", "x_flat", "e_meas", "x_meas")}}


def write_json(name, obj):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(obj, indent=1, default=str))
    return OUT / name
