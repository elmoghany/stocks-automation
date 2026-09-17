"""UNIVERSE+QUOTES (2026-09-16) -- constraint 2, stage 2: honest LIMIT fills.

The wide-net audit's measurement was that the toll IS the problem: the
regular-session unconditional expectancy is -$15..-$31 per $15,000 ticket
against a 20 bps round trip that costs $30, so the market part of the
expectancy is between zero and +$15 and the walk-forward ranker's real
+$24/ticket of skill lands at -$3.35. Its ranked idea #2 was to stop
paying the spread and start capturing it.

This module re-prices those tickets under a LIMIT entry instead of a
next-bar-open market fill, using the real tape.

WHAT "THE REAL TAPE" MEANS HERE (and what it cannot mean -- see uq_sec1)
  /v3/quotes and /v3/trades are 403 NOT_AUTHORIZED on this account, so
  there is no NBBO and no tick stream. There ARE 1-second aggregates, and
  a 1-second bar's `l` is the minimum TRADE price in that second. That is
  exactly, not approximately, what the fill rule needs.

THE FILL RULE, STATED SO THE POISON TEST CAN BE SCORED AGAINST IT
  At the decision instant t0 (= the start of minute m+1, the same instant
  the baseline table fills at), post a buy limit at
      L = mark(m) * (1 - k/10000)
  where mark(m) is the last printed close at or before minute m -- a
  quantity the poison test proves is a function of bars <= m only.
  The order FILLS iff some 1-second bar in (t0, t0 + N*60s] has l <= L.
  Fill price is L (never better, though a gap through the limit would in
  reality fill at or inside L -- the conservative side).
  If it does not fill, NO TRADE happens and the ticket books $0, exactly
  as a non-printing minute m+1 books $0 in the baseline table.

  The DECISION to post is a function of information <= t0 only.
  The FILL is revealed by prints strictly after t0. That asymmetry is
  legitimate and is the only honest way to grade an unexecuted limit; it
  is also the one thing the poison test must be allowed to see, and
  plan/uq_poison.py garbles everything after t0 EXCEPT the later prints
  that the fill rule is defined on, and asserts the posted limit price,
  the candidate set and the notional are bit-identical.

EXIT LEG
  Unchanged in shape from plan/rl2/features._targets: sell at the open of
  the first printed minute at or after (fill minute + H), or at the
  forced-flatten price. What changes is that the clock starts at the FILL
  minute, not at m+1, so a limit that fills three minutes late holds three
  minutes later. Exit cost is a parameter (`exit_bps`), default 10 bps --
  the incumbent assumption -- so the exit-side sensitivity is separable
  from the entry-side gain.

IDENTITY GATE
  `--stage selftest` recomputes the BASELINE ticket (market fill at the
  open of m+1, 10 bps a side, 20%-of-trailing-volume cap) from the raw
  day/feature caches and asserts it reproduces data/massive/wn/table.npz
  to within float32. If this module's day loading, indexing, notional or
  cost arithmetic drifted from the wide-net table, that gate fails and
  every number below is void.

Usage:
  python plan/uq_fills.py --stage selftest [--days 40]
  python plan/uq_fills.py --stage spread [--days 60]
"""
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import uq_sec1                                                # noqa: E402
from wn_lib import Table, write_json                          # noqa: E402

DAYS = HERE / "rl2" / "out" / "days"
FEAT = HERE / "rl2" / "out" / "feat"
OUT = HERE / "uq_out"
ET = ZoneInfo("America/New_York")

NMIN = 960
RTH_LO, RTH_HI = 330, 720
STEP = 5
STEPS = np.arange(0, NMIN - 5 + 1, STEP)
FEE_BPS, EXT_BPS = 10.0, 50.0
HORIZ = {"h15": 15, "h30": 30, "h60": 60, "h120": 120, "flat": 10 ** 6}
TICKET, MIN_NOTIONAL = 15000.0, 500.0
DEC_ET = ["07:00", "08:00", "09:00", "09:25", "09:35", "09:45", "10:00",
          "10:30", "11:00", "12:00", "13:00", "14:00", "15:00", "16:30"]
RTH_DEC = ["09:35", "09:45", "10:00", "10:30", "11:00", "12:00", "13:00",
           "14:00", "15:00"]


def cost_frac(minute, bps=FEE_BPS):
    ext = (np.asarray(minute) < RTH_LO) | (np.asarray(minute) >= RTH_HI)
    return (bps + EXT_BPS * ext) / 1e4


def next_printed(printed):
    """nxt[i,k] = smallest j >= k with printed[i,j], else NMIN."""
    S, N = printed.shape
    nxt = np.full((S, N + 1), N, np.int32)
    for k in range(N - 1, -1, -1):
        nxt[:, k] = np.where(printed[:, k], k, nxt[:, k + 1])
    return nxt[:, :N]


def dec_step(hhmm):
    """DEC_ET label -> index into the 5-minute STEPS grid."""
    h, m = (int(x) for x in hhmm.split(":"))
    g = h * 60 + m - 240
    assert g % STEP == 0 and 0 <= g <= STEPS[-1], hhmm
    return g // STEP


# dec_i (index into DEC_ET, the wide-net table's own column) -> STEPS index.
# wn_table.py stores `dec_i` against DEC_ET and slices the (T,S) feature
# arrays with DEC_T, so anything that reads mark/volcap/fill_o with a raw
# dec_i is off by a whole grid. Kept as one array so it cannot drift.
DEC_T = np.array([dec_step(x) for x in DEC_ET], np.int32)


# --------------------------------------------------------------- the day
class DayTape:
    """Minute grid + 1-second tape for one date."""

    def __init__(self, date, need_tape=True):
        self.date = date
        z = np.load(DAYS / f"{date}.npz", allow_pickle=False)
        self.syms = [str(s) for s in z["syms"]]
        self.sidx = {s: i for i, s in enumerate(self.syms)}
        self.o = z["o"].astype(np.float64)
        self.h = z["h"].astype(np.float64)
        self.l = z["l"].astype(np.float64)
        self.c = z["c"].astype(np.float64)
        self.v = z["v"].astype(np.float64)
        self.printed = ~np.isnan(self.c)
        self.nxt = next_printed(self.printed)
        any_p = self.printed.any(axis=1)
        last = np.where(any_p, NMIN - 1 - np.argmax(self.printed[:, ::-1],
                                                   axis=1), -1)
        self.flat_min = last.astype(np.int32)
        self.flat_px = np.where(last >= 0,
                                self.c[np.arange(len(self.syms)),
                                       np.maximum(last, 0)], np.nan)
        f = np.load(FEAT / f"{date}.npz", allow_pickle=False)
        self.mark = f["mark"].astype(np.float64)        # (T,S)
        self.volcap = f["volcap"].astype(np.float64)
        self.fill_o = f["fill_o"].astype(np.float64)
        self.prn_step = f["printed"]
        self.t0_04 = int(datetime(*(int(x) for x in date.split("-")),
                                  4, 0, tzinfo=ET).timestamp()) * 1000
        self._tape = {} if need_tape else None

    # ---- tape
    def tape(self, sym):
        if self._tape is None:
            return None
        if sym not in self._tape:
            self._tape[sym] = uq_sec1.load(sym, self.date)
        return self._tape[sym]

    def ms_of_min(self, minute):
        return self.t0_04 + minute * 60_000

    # ---- the trade
    def exit_leg(self, si, from_min, H):
        """(exit price, exit minute) for a position opened at `from_min`."""
        want = min(from_min + H, NMIN - 1)
        xi = int(self.nxt[si, want])
        if xi >= NMIN or xi > self.flat_min[si] or H >= NMIN:
            return float(self.flat_px[si]), int(self.flat_min[si])
        return float(self.o[si, xi]), xi

    def baseline(self, ti, si, h):
        """The wide-net table's own ticket, recomputed from raw caches.
        `ti` indexes the 5-minute STEPS grid (use DEC_T[dec_i])."""
        m = int(STEPS[ti])
        me = min(m + 1, NMIN - 1)
        if not self.printed[si, me]:
            return 0.0, False
        ent = float(self.o[si, me])
        notion = min(TICKET, self.volcap[ti, si] * ent)
        # NOTE, and it is a real convention not a nicety: wn_table.py
        # applies the $500 floor to the `printed`/`ok` FLAGS but leaves
        # `pnl` = notional * (1+cf) * tgt untouched, and wn_lib.mask()
        # gates candidates on `printed_m` alone -- so the wide-net study
        # DID book sub-$500 tickets at their true size. Reproducing that
        # exactly is what makes this an identity gate rather than an
        # approximation; the incidence is reported separately.
        if not np.isfinite(notion):
            return 0.0, False
        ex_px, ex_m = self.exit_leg(si, me, HORIZ[h])
        if not np.isfinite(ex_px) or ex_m < me:
            return 0.0, False
        r = (ex_px * (1 - cost_frac(ex_m))) / (ent * (1 + cost_frac(me))) - 1
        return notion * (1 + cost_frac(me)) * r, True

    def limit(self, ti, si, h, k_bps, nmin, passive_bps=0.0,
              exit_bps=FEE_BPS, cap_mult=1.0):
        """One limit-entry ticket. Returns a dict; `filled` False = $0.
        `ti` indexes the 5-minute STEPS grid (use DEC_T[dec_i])."""
        m = int(STEPS[ti])
        me = min(m + 1, NMIN - 1)
        ref = self.mark[ti, si]
        out = {"filled": False, "pnl": 0.0, "L": np.nan, "notional": 0.0,
               "fill_min": -1, "wait_s": np.nan, "capped": False}
        if not np.isfinite(ref) or ref <= 0:
            return out
        L = float(ref) * (1.0 - k_bps / 1e4)
        out["L"] = L
        rows = self.tape(self.syms[si])
        if not rows:
            return out
        lo_ms = self.ms_of_min(me)
        hi_ms = lo_ms + int(nmin * 60_000)
        ft = None
        for t, _o, _h, lw, _c, _v, _n in rows:
            if t < lo_ms:
                continue
            if t >= hi_ms:
                break
            if lw is not None and lw <= L:
                ft = t
                break
        if ft is None:
            return out
        mf = int((ft - self.t0_04) // 60_000)
        cap = self.volcap[ti, si] * cap_mult
        notion = min(TICKET, cap * L)
        if not np.isfinite(notion):
            return out
        ex_px, ex_m = self.exit_leg(si, mf, HORIZ[h])
        if not np.isfinite(ex_px) or ex_m < mf:
            return out
        ent_c = float(cost_frac(mf, passive_bps))
        ex_c = float(cost_frac(ex_m, exit_bps))
        r = (ex_px * (1 - ex_c)) / (L * (1 + ent_c)) - 1
        out.update(filled=True, pnl=notion * (1 + ent_c) * r,
                   notional=notion, fill_min=mf,
                   wait_s=(ft - lo_ms) / 1000.0,
                   capped=bool(cap * L < TICKET),
                   tiny=bool(notion < MIN_NOTIONAL))
        return out


# ----------------------------------------------------- spread estimators
def _pairs(hi, lo, cl):
    ok = np.isfinite(hi) & np.isfinite(lo) & np.isfinite(cl) & (lo > 0)
    return hi[ok], lo[ok], cl[ok]


def corwin_schultz(hi, lo):
    """Corwin & Schultz (2012) high-low spread, as a FRACTION of price.
    Consecutive-bar estimator; negative estimates are set to 0, which is
    the standard treatment and the conservative one here (a zero spread
    makes the LIMIT entry look worse, not better, relative to market)."""
    hi, lo = np.asarray(hi, float), np.asarray(lo, float)
    if hi.size < 2:
        return np.nan
    b = np.log(hi[:-1] / lo[:-1]) ** 2 + np.log(hi[1:] / lo[1:]) ** 2
    h2 = np.maximum(hi[:-1], hi[1:])
    l2 = np.minimum(lo[:-1], lo[1:])
    g = np.log(h2 / l2) ** 2
    k = 3 - 2 * np.sqrt(2)
    a = (np.sqrt(2 * b) - np.sqrt(b)) / k - np.sqrt(g / k)
    s = 2 * (np.exp(a) - 1) / (1 + np.exp(a))
    s = np.where(np.isfinite(s), s, np.nan)
    return float(np.nanmean(np.maximum(s, 0.0))) if np.isfinite(s).any() \
        else np.nan


def abdi_ranaldo(hi, lo, cl):
    """Abdi & Ranaldo (2017) close-high-low spread, as a fraction."""
    hi, lo, cl = (np.asarray(x, float) for x in (hi, lo, cl))
    if cl.size < 3:
        return np.nan
    eta = (np.log(hi) + np.log(lo)) / 2.0
    c = np.log(cl)
    x = 4.0 * (c[1:-1] - eta[1:-1]) * (c[1:-1] - eta[2:])
    x = x[np.isfinite(x)]
    if x.size == 0:
        return np.nan
    return float(np.sqrt(max(np.mean(x), 0.0)))


def roll(cl):
    """Roll (1984) serial-covariance spread, as a fraction. NaN when the
    covariance is positive (the estimator is undefined there, which is
    common intraday -- reported rather than floored)."""
    c = np.log(np.asarray(cl, float))
    d = np.diff(c)
    d = d[np.isfinite(d)]
    if d.size < 3:
        return np.nan
    cv = float(np.cov(d[:-1], d[1:])[0, 1])
    return 2.0 * np.sqrt(-cv) if cv < 0 else np.nan


def spread_at(day, si, ti, lookback_min=30):
    """The three estimators on the MINUTE bars ending at decision minute m
    (causal: bars with index <= m only), in bps of price."""
    m = int(STEPS[ti])
    a = max(0, m - lookback_min + 1)
    sl = slice(a, m + 1)
    hi, lo, cl = _pairs(day.h[si, sl], day.l[si, sl], day.c[si, sl])
    if hi.size < 3:
        return {"cs": np.nan, "ar": np.nan, "roll": np.nan, "n": int(hi.size)}
    return {"cs": corwin_schultz(hi, lo) * 1e4,
            "ar": abdi_ranaldo(hi, lo, cl) * 1e4,
            "roll": roll(cl) * 1e4, "n": int(hi.size)}


def obs_spread_sec(day, sym, ti, lookback_s=300, min_n=10):
    """DIRECTLY OBSERVED intra-second price dispersion, in bps.

    Not an estimator and not a model: for every 1-second bar in the
    lookback that carried at least `min_n` transactions, (h - l) / mid is
    the range the tape actually printed inside one second. When trades
    alternate between the bid and the offer -- the normal state of a
    liquid tape -- that range IS the inside spread, which is why this is
    the number reported as the headline in universe-quotes-audit.md and
    the two published high-low ESTIMATORS are reported beside it.

    `min_n` matters and is not arbitrary. In a second with n prints the
    range is the spread only if BOTH sides were hit; at n = 2 that happens
    about half the time, so the median range over low-n seconds is a
    mechanical ZERO and understates badly (measured: median 0.0 bps at
    n >= 2). At n >= 10 both sides are hit with near-certainty and the
    median range converges on the spread from below, with a small upward
    contamination from genuine drift inside the second. n >= 10 is the
    default for that reason and the whole n-bucket table is printed by
    `--stage spread` so the convergence is visible rather than asserted.
    """
    rows = day.tape(sym)
    if not rows:
        return np.nan, 0
    me = min(int(STEPS[ti]) + 1, NMIN - 1)
    hi_ms = day.ms_of_min(me)
    lo_ms = hi_ms - lookback_s * 1000
    vals = []
    for t, _o, h, l, _c, _v, n in rows:
        if t < lo_ms:
            continue
        if t >= hi_ms:
            break
        if n is None or n < min_n or h is None or l is None or l <= 0:
            continue
        vals.append((h - l) / ((h + l) / 2.0) * 1e4)
    if not vals:
        return np.nan, 0
    return float(np.median(vals)), len(vals)


def spread_sec(day, sym, ti, lookback_s=300):
    """Same three estimators on the 1-SECOND tape ending at t0 (causal)."""
    rows = day.tape(sym)
    if not rows:
        return {"cs": np.nan, "ar": np.nan, "roll": np.nan, "n": 0}
    me = min(int(STEPS[ti]) + 1, NMIN - 1)
    hi_ms = day.ms_of_min(me)
    lo_ms = hi_ms - lookback_s * 1000
    w = [r for r in rows if lo_ms <= r[0] < hi_ms]
    if len(w) < 3:
        return {"cs": np.nan, "ar": np.nan, "roll": np.nan, "n": len(w)}
    hi = np.array([r[2] for r in w], float)
    lo = np.array([r[3] for r in w], float)
    cl = np.array([r[4] for r in w], float)
    hi, lo, cl = _pairs(hi, lo, cl)
    if hi.size < 3:
        return {"cs": np.nan, "ar": np.nan, "roll": np.nan, "n": int(hi.size)}
    return {"cs": corwin_schultz(hi, lo) * 1e4,
            "ar": abdi_ranaldo(hi, lo, cl) * 1e4,
            "roll": roll(cl) * 1e4, "n": int(hi.size)}


# -------------------------------------------------------------- selftest
def stage_selftest(ndays=40, seed=0):
    t = Table()
    rng = np.random.default_rng(seed)
    dates = list(t.dates)
    pick = sorted(rng.choice(len(dates), min(ndays, len(dates)),
                             replace=False))
    n_chk = n_bad = 0
    worst = 0.0
    for di_d in pick:
        date = dates[di_d]
        day = DayTape(date, need_tape=False)
        rows = np.flatnonzero((t.date_i == di_d) & t.printed_m)
        if rows.size == 0:
            continue
        sel = rng.choice(rows, min(600, rows.size), replace=False)
        for r in sel:
            sym = t.syms[t.sym_i[r]]
            si = day.sidx.get(sym)
            if si is None:
                continue
            for h in ("h15", "h30", "h60", "h120", "flat"):
                got, _ok = day.baseline(int(DEC_T[t.dec_i[r]]), si, h)
                want = float(t.pnl[h][r])
                n_chk += 1
                d = abs(got - want)
                tol = max(1e-3, 2e-5 * max(abs(want), 1.0))
                if d > tol:
                    n_bad += 1
                    worst = max(worst, d)
    print(f"SELFTEST: {n_chk:,} ticket recomputations over {len(pick)} days, "
          f"{n_bad:,} mismatches (worst |diff| ${worst:.4f})")
    write_json("../../plan/uq_out/selftest.json",
               {"checks": n_chk, "mismatches": n_bad, "worst": worst,
                "days": len(pick)}) if False else \
        (OUT / "selftest.json").write_text(json.dumps(
            {"checks": n_chk, "mismatches": n_bad, "worst": worst,
             "days": len(pick)}, indent=1))
    if n_bad:
        raise SystemExit("IDENTITY GATE FAILED -- numbers below are void")


# ---------------------------------------------------------------- spread
def obs_spread_buckets(day, sym, ti, lookback_s=300,
                       buckets=(2, 5, 10, 20, 50)):
    """Median 1-second high-low range, in bps, per minimum-transaction
    bucket. Prints the convergence the `min_n` choice rests on."""
    rows = day.tape(sym)
    out = {}
    if not rows:
        return out
    me = min(int(STEPS[ti]) + 1, NMIN - 1)
    hi_ms = day.ms_of_min(me)
    lo_ms = hi_ms - lookback_s * 1000
    vals = []
    for t, _o, h, l, _c, _v, n in rows:
        if t < lo_ms:
            continue
        if t >= hi_ms:
            break
        if n is None or h is None or l is None or l <= 0:
            continue
        vals.append((n, (h - l) / ((h + l) / 2.0) * 1e4))
    for b in buckets:
        v = [x for n, x in vals if n >= b]
        out[b] = (float(np.median(v)), len(v)) if v else (np.nan, 0)
    return out


def stage_spread(ndays=60, seed=0, per_day=120):
    t = Table()
    rng = np.random.default_rng(seed)
    dates = list(t.dates)
    pick = sorted(rng.choice(len(dates), min(ndays, len(dates)),
                             replace=False))
    dec_idx = [DEC_ET.index(d) for d in RTH_DEC]
    rec = []
    for di_d in pick:
        date = dates[di_d]
        if not any(uq_sec1.have(s, date) for s in ("AAOI",)):
            pass
        day = DayTape(date)
        rows = np.flatnonzero((t.date_i == di_d) & t.printed_m
                              & np.isin(t.dec_i, dec_idx))
        if rows.size == 0:
            continue
        sel = rng.choice(rows, min(per_day, rows.size), replace=False)
        for r in sel:
            sym = t.syms[t.sym_i[r]]
            si = day.sidx.get(sym)
            if si is None or not uq_sec1.have(sym, date):
                continue
            di = int(t.dec_i[r])
            ti = int(DEC_T[di])
            mn = spread_at(day, si, ti)
            sc = spread_sec(day, sym, ti)
            bk = obs_spread_buckets(day, sym, ti)
            rec.append({"date": date, "sym": sym, "dec": DEC_ET[di],
                        "px": float(day.mark[ti, si]),
                        **{f"obs_n{b}": bk.get(b, (np.nan, 0))[0]
                           for b in (2, 5, 10, 20, 50)},
                        "m_cs": mn["cs"], "m_ar": mn["ar"], "m_roll": mn["roll"],
                        "s_cs": sc["cs"], "s_ar": sc["ar"], "s_roll": sc["roll"],
                        "s_n": sc["n"]})
    if not rec:
        print("no rows -- is the 1-second tape cached?")
        return
    def pct(key):
        v = np.array([r[key] for r in rec], float)
        v = v[np.isfinite(v)]
        if v.size == 0:
            return None
        q = np.percentile(v, [10, 25, 50, 75, 90])
        return {"n": int(v.size), "mean": round(float(v.mean()), 2),
                "p10": round(q[0], 2), "p25": round(q[1], 2),
                "p50": round(q[2], 2), "p75": round(q[3], 2),
                "p90": round(q[4], 2)}
    rep = {"rows": len(rec), "days": len(pick),
           "estimators_bps": {k: pct(k) for k in
                              ("m_cs", "m_ar", "m_roll",
                               "s_cs", "s_ar", "s_roll")},
           "observed_1s_range_bps_by_min_transactions":
               {b: pct(f"obs_n{b}") for b in (2, 5, 10, 20, 50)}}
    print(json.dumps(rep, indent=1))
    (OUT / "spread_report.json").write_text(json.dumps(
        {**rep, "sample": rec[:4000]}, indent=1, default=str))


if __name__ == "__main__":
    a = sys.argv
    st = a[a.index("--stage") + 1] if "--stage" in a else "selftest"
    nd = int(a[a.index("--days") + 1]) if "--days" in a else None
    OUT.mkdir(parents=True, exist_ok=True)
    if st == "selftest":
        stage_selftest(nd or 40)
    elif st == "spread":
        stage_spread(nd or 60)
    else:
        raise SystemExit(f"unknown stage {st}")
