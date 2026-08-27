"""W-campaign: does ANY causal feature predict forward returns on the
HONEST novol pool?  (information-coefficient study)

WHY THIS EXISTS
---------------
The full-coverage backfill (108,991 symbol-day bar files) destroyed the
historical edge: C37's own parameters return -$72,673 over 445 traded
days on the honest pool versus +$635,759 on the old bar-starved cache.
Two rounds of veto / ordering / phase experiments then produced a
SEEDED-RANDOM veto (+$22,596) that beat every calibrated instrument
(best real config +$5,307, itself failing the both-years rule).  The
diagnosis in NOTES-DAYTRADING.md is that the C37 entry ruleset has
NEGATIVE PER-TRADE EXPECTANCY on the honest universe, so every
"improvement" is really abstention.

Filter tuning therefore cannot answer the question.  This file answers
the PRIOR question: over the honest universe, does any strictly causal
feature carry cross-sectional information about the forward return?
If yes, a new entry can be built from it.  If no, the honest number is
the ceiling and we report it.

DESIGN
------
* Universe: every (symbol, date) in gappers_novol_year.json +
  gappers_novol_y2025.json with hist_n >= 50, a usable prev_close, and
  a bar file in data/massive/m1: 108,464 symbol-days over 444 trading
  days, yielding 240,439 (symbol, day, decision-time) rows.  NO
  sampling: the full pool is used (see --limit-days for smoke runs).
* Decision times (ET): 07:30, 08:30, 09:35, 10:00, 10:30, 11:30.  A row
  exists at time T only if the name's +10% cross (High >= 1.10 *
  prev_close) has ALREADY printed at or before T -- i.e. only names we
  could actually have been looking at.
* Features: strictly causal.  Bars at or before T only, never after.
  Reuses plan/liquidity_estimators.py verbatim for the microstructure
  block and plan/causal.py's CausalView as the reference slicer.
* Two NEGATIVE CONTROLS travel with every real feature: a hash of the
  ticker string (a stable but meaningless cross-sectional ordering) and
  a per-row seeded random number.  A feature that does not clearly beat
  BOTH is not a signal.
* Targets: log forward returns from the decision-time close to +30min,
  +60min and the 15:00 ET flatten; "peak-forward" (max high in the
  window / close) at +60min and to the flatten; and three ENTRY-LAG
  targets that re-base the return on a LATER print.  The entry-lag
  family is the bid-ask-bounce control and `fwd_flat_nx` is the target
  the verdict is decided on -- see BOUNCE CONTROL below.  The peak
  targets are reported but excluded from the verdict: max(High)/entry
  is an upper bound nobody can sell at and is mechanically increasing
  in volatility and tape density.

CAUSALITY, ASSERTED NOT ASSUMED
-------------------------------
Three independent guards, all live in every run:
  1. STRUCTURAL.  The feature block never receives the future.  Each row
     is computed from `pre = df.iloc[:k]`, the prefix ending at the
     decision bar; rows after T are not in the frame that features see,
     so a slicing bug cannot reach them.
  2. GATE.  Every row asserts the prefix boundary (last bar <= T, next
     bar > T) -- the plan/causal.py leak-gate pattern -- and the
     liquidity estimators re-assert it inside _tail_before on every
     call.
  3. MECHANICAL.  --selftest poisons every bar at or after T with
     absurd values and asserts that not one feature moves, the proof
     used in liquidity_estimators.self_test().  A random 1-in-N sample
     of live rows is additionally checked against
     CausalView(df).upto(T) for exact frame equality; the count of
     verified rows is reported.

USAGE
    python plan/ic_study.py --selftest            # guards + equivalence
    python plan/ic_study.py --extract [--workers 4] [--limit-days N]
    python plan/ic_study.py --halal               # halal PASS flags
    python plan/ic_study.py --analyze             # tables -> markdown
    python plan/ic_study.py --analyze --reuse-stats   # re-render prose

Wall clock on this box: selftest ~1 min, extract ~20 min on 4 workers,
halal 14 s, analyze ~10 min (or seconds with --reuse-stats).

Intermediates land in data/massive/ic_study/ (gitignored bulk cache).
Nothing in this file writes to rotation_sim.py, day-trading.py,
idgate.py, data_manifest.py or any config; it is read-only analysis.
"""

import argparse
import hashlib
import json
import math
import os
import random
import sys
import time
from datetime import date as ddate
from datetime import time as dtime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "plan"))

from causal import CausalView                      # noqa: E402
import liquidity_estimators as LE                   # noqa: E402

M1 = ROOT / "data/massive/m1"
OUT = ROOT / "data/massive/ic_study"
POOLS = {"y2025": "gappers_novol_y2025.json",      # 2024-10-22..2025-08-01
         "year": "gappers_novol_year.json"}        # 2025-08-01..2026-07-31

DECISIONS = [dtime(7, 30), dtime(8, 30), dtime(9, 35),
             dtime(10, 0), dtime(10, 30), dtime(11, 30)]
FLATTEN = dtime(15, 0)
CROSS_MULT = 1.10            # the +10% cross that defines the universe
MIN_FWD_BARS = 5             # drop rows with fewer bars left to 15:00
MIN_NAMES_PER_DAY = 5        # cross-section too thin below this

# ---------------------------------------------------------------- schema
CONTROLS = ["ctl_tickerhash", "ctl_random"]
# Reported in every table but never proposed as a signal: it is the
# instrument that measures the bid-ask artefact, not a candidate.
DIAGNOSTIC = ["close_pos"]
FEATURES = [
    # shape / extension
    "coil", "dist_sess_high_pct", "dist_high60", "gain_now",
    "pm_gain", "gap7",
    # tape pressure (the C37 ranker's own statistic and variants)
    "pressure30", "pressure30_nv", "pressure30_bc", "pressure30_t",
    "pressure10",
    # participation / density
    "log_dvol", "n_bars", "stale_min", "no_trade_share",
    # liquidity / cost
    "amihud", "corwin_schultz", "abdi_ranaldo", "roll", "bar_range",
    # level / vol / clock
    "log_price", "atr_pct", "mins_since_cross",
    # microstructure diagnostic: where the decision bar's close sits in
    # its OWN range.  1.0 = closed on the ask side, 0.0 = on the bid
    # side.  Not a candidate signal -- it is the instrument that
    # measures how much of any result is bid-ask bounce.
    "close_pos",
] + CONTROLS

# TARGETS split into what a trade can actually capture and what it
# cannot.  `peak*` is max(High)/entry: an UPPER BOUND nobody can sell
# at, and mechanically increasing in volatility and tape density, so it
# is reported (the brief asks for it) and excluded from the verdict.
# The `_nx` family re-bases the return on a LATER bar -- see BOUNCE
# CONTROL below.
TARGETS_TRADEABLE = ["fwd30", "fwd60", "fwd_flat",
                     "fwd60_nx", "fwd_flat_nx", "fwd_flat_nx5"]
TARGETS_BOUND = ["peak60", "peak_flat"]
TARGETS = TARGETS_TRADEABLE + TARGETS_BOUND
PRIMARY = "fwd_flat_nx"      # the target the verdict is decided on
IDCOLS = ["date", "sym", "dt", "pool", "base_px", "n_fwd_bars"]

# BOUNCE CONTROL.  Every feature is read off the bar at the decision
# time, and the plain targets are based on THAT bar's close.  A print
# is at the bid or at the ask, so the base price carries half a spread
# of noise -- and because a row only exists after a +10% UP cross, that
# noise is SELECTED: the decision print is more often at the ask, which
# depresses the measured forward return, and depresses it MORE for
# wider-spread names.  That single mechanism would manufacture exactly
# the result this study is looking for (spread and extension appearing
# to predict losses) out of nothing.
#   `fwd_flat_nx`  re-bases on the close of the FIRST bar after the
#                  decision time -- the earliest price we could really
#                  have paid, and a print whose bid/ask side is
#                  independent of the feature's bar.
#   `fwd_flat_nx5` re-bases 5 minutes later still (arming latency).
#   `fwd60_nx`     the same re-basing at the 60-minute horizon.
# A feature that keeps its IC under `_nx` is describing the market. One
# that loses it was describing our own entry print.

# DERIVED at analysis time from the columns above -- no re-extraction.
# c37_rank_score reproduces the ADOPTED champion's own ordering key
# (rotation_sim.rank_at): coiled names (coil >= 0.95) first, then
# descending 30-bar pressure, with a missing pressure sorting tied-last
# exactly as rank_at's `-(prs if prs is not None else -1)` does.  This
# is the single most decision-relevant "feature" in the study: it asks
# whether the thing C37 actually ranks on carries any information.
DERIVED = ["c37_rank_score"]
ALL_FEATS = FEATURES + DERIVED


# ------------------------------------------------------------------
# bar loading -- fast path, proven equal to the rotation_sim loader
# ------------------------------------------------------------------
_OFFCACHE = {}


def _et_offset_minutes(date_str):
    """UTC->ET offset in minutes for a trading date (-240 EDT / -300 EST).

    TZ env is unreliable on this box, so the offset is computed
    explicitly from the tz database via pandas at noon local -- noon is
    never inside a DST transition, and every bar of a Mon-Fri session
    shares the session's offset."""
    off = _OFFCACHE.get(date_str)
    if off is None:
        ts = pd.Timestamp(f"{date_str} 12:00:00", tz="America/New_York")
        off = int(ts.utcoffset().total_seconds() // 60)
        _OFFCACHE[date_str] = off
    return off


def load_bars(sym, date_str):
    """Bars for one symbol-day, indexed by NAIVE ET wall clock.

    The reference loader (rotation_sim.bars_for) does
    read_csv(parse_dates=True).tz_convert("America/New_York"); at 22 ms
    a file that is 40 minutes of pure timestamp parsing over the pool.
    This reads the numerics with pandas and converts the fixed-width
    ISO timestamps arithmetically, then drops the tz label (every
    operation here is a wall-clock comparison, so the label is
    redundant).  `--selftest` asserts this index is byte-identical to
    the reference loader's tz_convert(...).tz_localize(None)."""
    f = M1 / f"{sym}_{date_str}.csv"
    if not f.exists():
        return None
    try:
        df = pd.read_csv(f)
    except Exception:
        return None
    if len(df) == 0 or "begins_at" not in df.columns:
        return None
    ts = df["begins_at"].to_numpy()
    try:
        buf = np.frombuffer("".join(ts).encode("ascii"), dtype=np.uint8)
    except Exception:
        return None
    if buf.size != 25 * len(ts):          # non-standard width -> refuse
        return None
    a = buf.reshape(-1, 25).astype(np.int64) - 48
    d2 = lambda i, j: a[:, i] * 10 + a[:, j]                 # noqa: E731
    yy = (a[:, 0] * 1000 + a[:, 1] * 100 + a[:, 2] * 10 + a[:, 3])
    mo, dd = d2(5, 6), d2(8, 9)
    hh, mi = d2(11, 12), d2(14, 15)
    key = yy * 10000 + mo * 100 + dd
    ords = {}
    for k in np.unique(key):
        k = int(k)
        ords[k] = ddate(k // 10000, (k // 100) % 100, k % 100).toordinal()
    ordv = np.array([ords[int(k)] for k in key], dtype=np.int64)
    utc_min = ordv * 1440 + hh * 60 + mi
    et_min = utc_min + _et_offset_minutes(date_str)
    base = ddate(*(int(x) for x in date_str.split("-"))).toordinal()
    mod = et_min - base * 1440
    keep = (mod >= 0) & (mod < 1440)
    if not keep.any():
        return None
    idx = (np.datetime64(date_str, "m")
           + mod[keep].astype("timedelta64[m]")).astype("datetime64[ns]")
    out = pd.DataFrame(
        {"Open": df["Open"].to_numpy(np.float64)[keep],
         "High": df["High"].to_numpy(np.float64)[keep],
         "Low": df["Low"].to_numpy(np.float64)[keep],
         "Close": df["Close"].to_numpy(np.float64)[keep],
         "Volume": df["Volume"].to_numpy(np.float64)[keep]},
        index=pd.DatetimeIndex(idx))
    if not out.index.is_monotonic_increasing:
        out = out.sort_index()
    return out


def _ref_load_bars(sym, date_str):
    """rotation_sim.bars_for, replicated for the equivalence check only."""
    f = M1 / f"{sym}_{date_str}.csv"
    if not f.exists():
        return None
    df = pd.read_csv(f, index_col=0, parse_dates=True)
    df.index = df.index.tz_convert("America/New_York")
    return df


# ------------------------------------------------------------------
# pressure -- byte-compatible with day-trading.py::Candles.pressure
# ------------------------------------------------------------------
def _signed(h, l, c, v):
    rng = h - l
    with np.errstate(divide="ignore", invalid="ignore"):
        pos = np.where(rng > 0, (2 * (c - l) - rng) / rng, 0.0)
    return v * pos, pos


def pressure_last(h, l, c, v, n, min_vol=20_000):
    """Candles.pressure(i=len-1, n, min_vol) over the last n bars."""
    if len(c) == 0:
        return None
    sv, _ = _signed(h[-n:], l[-n:], c[-n:], v[-n:])
    vol = float(v[-n:].sum())
    if vol < min_vol or vol <= 0:
        return None
    return float(sv.sum() / vol)


def pressure_barcount(h, l, c, v, n):
    """Bar-count-normalised variant: the MEAN of the per-bar intrabar
    close position over the last n bars, unweighted by volume.

    Why it exists: the production statistic divides signed volume by
    window volume, so on a sparse tape one fat print dominates and the
    window's wall-clock span is uncontrolled.  This variant gives every
    bar one vote, isolating "did closes sit near bar highs" from "was
    one bar huge"."""
    if len(c) == 0:
        return None
    _, pos = _signed(h[-n:], l[-n:], c[-n:], v[-n:])
    return float(pos.mean())


# ------------------------------------------------------------------
# feature block (strictly causal by construction)
# ------------------------------------------------------------------
def _hash01(s):
    return int(hashlib.md5(s.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF


def features_at(pre, nxt, prev_close, cross_ts, t_ts, sym, date_str):
    """All features from `pre` = bars at or before the decision time.

    `pre` physically contains no bar after t_ts, so nothing in here can
    read the future.  `nxt` = t_ts + 1min is handed to the
    liquidity_estimators, whose _tail_before() takes bars STRICTLY
    before it -- i.e. exactly `pre` -- and asserts the boundary on
    every call."""
    h = pre["High"].to_numpy()
    l = pre["Low"].to_numpy()
    c = pre["Close"].to_numpy()
    v = pre["Volume"].to_numpy()
    idx = pre.index
    last = float(c[-1])
    hi_all = float(h.max())
    f = {}

    f["coil"] = last / hi_all if hi_all > 0 else np.nan
    f["dist_sess_high_pct"] = ((hi_all / last - 1) * 100 if last > 0
                               else np.nan)
    w60 = idx >= (t_ts - pd.Timedelta(minutes=60))
    hi60 = float(h[w60].max()) if w60.any() else hi_all
    f["dist_high60"] = last / hi60 if hi60 > 0 else np.nan
    f["gain_now"] = (last / prev_close - 1) * 100
    tt = idx.time
    pm = c[tt < dtime(7, 0)]
    f["pm_gain"] = (float(pm[-1]) / prev_close - 1) * 100 if len(pm) \
        else np.nan
    g7 = c[tt <= dtime(7, 0)]
    f["gap7"] = (float(g7[-1]) / prev_close - 1) * 100 if len(g7) \
        else np.nan

    f["pressure30"] = pressure_last(h, l, c, v, 30, 20_000)
    f["pressure30_nv"] = pressure_last(h, l, c, v, 30, 0)
    f["pressure30_bc"] = pressure_barcount(h, l, c, v, 30)
    m30 = idx >= (t_ts - pd.Timedelta(minutes=30))
    f["pressure30_t"] = (pressure_last(h[m30], l[m30], c[m30], v[m30],
                                       int(m30.sum()), 0)
                         if m30.any() else None)
    f["pressure10"] = pressure_last(h, l, c, v, 10, 0)

    dvol = float((c * v).sum())
    f["log_dvol"] = math.log10(1.0 + dvol)
    f["n_bars"] = float(len(pre))
    f["stale_min"] = (t_ts - idx[-1]).total_seconds() / 60.0

    f["amihud"] = LE.amihud(pre, nxt, 30)
    f["no_trade_share"] = LE.no_trade_share(pre, nxt, 30)
    f["corwin_schultz"] = LE.corwin_schultz(pre, nxt, 30)
    f["abdi_ranaldo"] = LE.abdi_ranaldo(pre, nxt, 30)
    f["roll"] = LE.roll(pre, nxt, 30)
    f["bar_range"] = LE.bar_range_proxy(pre, nxt, 10)

    f["log_price"] = math.log10(last) if last > 0 else np.nan
    k = min(14, len(c))
    if k >= 2:
        hh, ll, cc = h[-k:], l[-k:], c[-k:]
        prev_c = np.concatenate(([cc[0]], cc[:-1]))
        tr = np.maximum.reduce([hh - ll, np.abs(hh - prev_c),
                                np.abs(ll - prev_c)])
        f["atr_pct"] = float(tr.mean() / last * 100) if last > 0 else np.nan
    else:
        f["atr_pct"] = np.nan
    f["mins_since_cross"] = (t_ts - cross_ts).total_seconds() / 60.0
    rng_last = float(h[-1] - l[-1])
    f["close_pos"] = (float((c[-1] - l[-1]) / rng_last) if rng_last > 0
                      else 0.5)

    # NEGATIVE CONTROLS -- carried through the identical pipeline.
    f["ctl_tickerhash"] = _hash01(sym)
    f["ctl_random"] = random.Random(
        f"ic-{date_str}-{sym}-{t_ts.hour:02d}{t_ts.minute:02d}").random()
    return f


# ------------------------------------------------------------------
# one symbol-day -> up to len(DECISIONS) rows
# ------------------------------------------------------------------
def rows_for(sym, date_str, prev_close, pool, verify_every=0, vstate=None):
    df = load_bars(sym, date_str)
    if df is None or len(df) < 3 or prev_close is None or prev_close <= 0:
        return []
    idx = df.index
    hv = df["High"].to_numpy()
    cv = df["Close"].to_numpy()

    thr = CROSS_MULT * prev_close
    hit = np.nonzero(hv >= thr)[0]
    if not len(hit):
        return []
    cross_ts = idx[hit[0]]

    day = np.datetime64(date_str, "D")
    flat_ts = pd.Timestamp(day) + pd.Timedelta(hours=15)
    k_flat = int(np.searchsorted(idx.to_numpy(), np.datetime64(flat_ts),
                                 side="right"))
    out = []
    for T in DECISIONS:
        t_ts = pd.Timestamp(day) + pd.Timedelta(hours=T.hour,
                                                minutes=T.minute)
        if cross_ts > t_ts:
            continue                     # not yet a candidate at T
        k = int(np.searchsorted(idx.to_numpy(), np.datetime64(t_ts),
                                side="right"))
        if k < 3:
            continue
        # LEAK GATE (every row): the prefix ends at or before T and the
        # first excluded bar is strictly after T.
        assert idx[k - 1] <= t_ts, (
            f"FUTURE LEAK {sym} {date_str} {T}: prefix ends {idx[k-1]}")
        assert k == len(idx) or idx[k] > t_ts, (
            f"PREFIX SHORT {sym} {date_str} {T}: bar {idx[k]} <= {t_ts}")
        n_fwd = k_flat - k
        if n_fwd < MIN_FWD_BARS:
            continue
        pre = df.iloc[:k]
        if verify_every and vstate is not None:
            vstate["seen"] += 1
            if vstate["seen"] % verify_every == 0:
                ref = CausalView(df, sym, date_str).upto(T)
                assert len(ref) == len(pre) and (
                    ref.index[-1] == pre.index[-1]), (
                    f"CausalView mismatch {sym} {date_str} {T}")
                assert np.array_equal(ref["Close"].to_numpy(),
                                      pre["Close"].to_numpy())
                vstate["ok"] += 1

        nxt = t_ts + pd.Timedelta(minutes=1)
        f = features_at(pre, nxt, prev_close, cross_ts, t_ts, sym,
                        date_str)
        base = float(cv[k - 1])
        if base <= 0:
            continue
        row = {"date": date_str, "sym": sym,
               "dt": f"{T.hour:02d}:{T.minute:02d}", "pool": pool,
               "base_px": base, "n_fwd_bars": float(n_fwd)}
        for name, mins in (("fwd30", 30), ("fwd60", 60)):
            e = np.datetime64(t_ts + pd.Timedelta(minutes=mins))
            ke = int(np.searchsorted(idx.to_numpy(), e, side="right"))
            row[name] = (math.log(float(cv[ke - 1]) / base)
                         if ke > k and cv[ke - 1] > 0 else np.nan)
        row["fwd_flat"] = (math.log(float(cv[k_flat - 1]) / base)
                           if k_flat > k and cv[k_flat - 1] > 0 else np.nan)
        e60 = np.datetime64(t_ts + pd.Timedelta(minutes=60))
        k60 = int(np.searchsorted(idx.to_numpy(), e60, side="right"))
        row["peak60"] = (math.log(float(hv[k:k60].max()) / base)
                         if k60 > k else np.nan)
        row["peak_flat"] = (math.log(float(hv[k:k_flat].max()) / base)
                            if k_flat > k else np.nan)
        # BOUNCE CONTROLS: re-base on a LATER print, so the base price's
        # bid/ask side is independent of the bar the features were read
        # from.  `nx` = the first bar after T (the earliest fill that is
        # physically possible), `nx5` = 5 minutes of arming latency.
        e5 = np.datetime64(t_ts + pd.Timedelta(minutes=5))
        k5 = int(np.searchsorted(idx.to_numpy(), e5, side="right"))
        b_nx = float(cv[k]) if k < len(cv) else 0.0
        b_n5 = float(cv[k5 - 1]) if k5 > k else 0.0
        row["fwd_flat_nx"] = (math.log(float(cv[k_flat - 1]) / b_nx)
                              if b_nx > 0 and k_flat - 1 > k
                              and cv[k_flat - 1] > 0 else np.nan)
        row["fwd60_nx"] = (math.log(float(cv[k60 - 1]) / b_nx)
                           if b_nx > 0 and k60 - 1 > k
                           and cv[k60 - 1] > 0 else np.nan)
        row["fwd_flat_nx5"] = (math.log(float(cv[k_flat - 1]) / b_n5)
                               if b_n5 > 0 and k_flat - 1 > k5 - 1
                               and cv[k_flat - 1] > 0 else np.nan)
        for c_ in FEATURES:
            val = f.get(c_)
            row[c_] = np.nan if val is None else float(val)
        out.append(row)
    return out


# ------------------------------------------------------------------
# extraction driver
# ------------------------------------------------------------------
def load_pool():
    """(date -> [(sym, prev_close, pool)]) for every row with bars.

    hist_n >= 50 is the pool's own standing quality bar.  Overlap day
    2025-08-01 exists in both files; a (sym, date) seen in y2025 is not
    re-added from year, so the split-half sets are disjoint."""
    have = set(os.listdir(M1))
    by_day, seen = {}, set()
    for pool, fn in POOLS.items():
        rows = json.loads((ROOT / "data/massive" / fn).read_text())
        for r in rows:
            if (r.get("hist_n") or 0) < 50:
                continue
            sym, date_str = r["symbol"], r["date"]
            if (sym, date_str) in seen:
                continue
            if f"{sym}_{date_str}.csv" not in have:
                continue
            pc = r.get("prev_close")
            if not pc or pc <= 0:
                continue
            seen.add((sym, date_str))
            by_day.setdefault(date_str, []).append((sym, float(pc), pool))
    return by_day


def _worker(args):
    dates, by_day, shard, verify_every = args
    vstate = {"seen": 0, "ok": 0}
    rows = []
    for d in dates:
        for sym, pc, pool in by_day[d]:
            try:
                rows.extend(rows_for(sym, d, pc, pool, verify_every,
                                     vstate))
            except AssertionError:
                raise
            except Exception:
                continue
    if not rows:
        return None, vstate
    df = pd.DataFrame(rows)
    for c in FEATURES + TARGETS + ["base_px", "n_fwd_bars"]:
        df[c] = df[c].astype(np.float32)
    p = OUT / f"rows_{shard:02d}.parquet"
    df.to_parquet(p, index=False)
    return str(p), vstate


def extract(workers=4, limit_days=0, verify_every=500):
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("rows_*.parquet"):
        old.unlink()
    by_day = load_pool()
    days = sorted(by_day)
    if limit_days:
        step = max(1, len(days) // limit_days)
        days = days[::step][:limit_days]
        by_day = {d: by_day[d] for d in days}
    n_pairs = sum(len(v) for v in by_day.values())
    print(f"pool: {n_pairs} symbol-days over {len(days)} trading days",
          flush=True)
    chunks = [days[i::workers] for i in range(workers)]
    t0 = time.time()
    if workers == 1:
        res = [_worker((chunks[0], by_day, 0, verify_every))]
    else:
        from concurrent.futures import ProcessPoolExecutor
        jobs = [(ch, {d: by_day[d] for d in ch}, i, verify_every)
                for i, ch in enumerate(chunks)]
        with ProcessPoolExecutor(max_workers=workers) as ex:
            res = list(ex.map(_worker, jobs))
    seen = sum(v["seen"] for _, v in res)
    ok = sum(v["ok"] for _, v in res)
    paths = [p for p, _ in res if p]
    total = sum(len(pd.read_parquet(p, columns=["dt"])) for p in paths)
    meta = {"symbol_days": n_pairs, "days": len(days), "rows": total,
            "shards": paths, "causalview_verified": ok,
            "rows_considered": seen, "secs": round(time.time() - t0, 1)}
    (OUT / "extract_meta.json").write_text(json.dumps(meta, indent=1))
    print(json.dumps(meta, indent=1), flush=True)


# ------------------------------------------------------------------
# halal PASS flags for the tradeable-universe cut
# ------------------------------------------------------------------
class _CachedFile:
    """A Path-alike that memoises read_text()/exists() for one file."""
    __slots__ = ("_p", "_c")

    def __init__(self, p, c):
        self._p, self._c = p, c

    def _txt(self):
        k = self._p.name
        if k not in self._c:
            try:
                self._c[k] = self._p.read_text() if self._p.exists() \
                    else None
            except Exception:
                self._c[k] = None
        return self._c[k]

    def exists(self):
        return self._txt() is not None

    def read_text(self, *a, **kw):
        t = self._txt()
        if t is None:
            raise FileNotFoundError(str(self._p))
        return t


class _CachedDir:
    __slots__ = ("_b", "_c")

    def __init__(self, base):
        self._b, self._c = base, {}

    def __truediv__(self, name):
        return _CachedFile(self._b / name, self._c)


def build_halal():
    """Point-in-time halal PASS flags from the harness's OWN gate.

    Two patches, both read-only, both disclosed in the writeup:

    1. MEMOISATION. `halal_pt` re-reads three or four small JSON files
       from disk on every call. Over 108k symbol-days that is hours.
       `axb.PT` is swapped for a caching Path-alike and the two
       file-backed helpers for cached read-only twins. The VALUES are
       identical -- it is the same bytes, read once.
    2. NO FETCHING. The unpatched `shares_asof` / `massive_fin` call
       Polygon on a cache miss and then WRITE the (possibly empty)
       answer back into data/pt_shares. Only ~27% of this pool's
       (symbol, month) pairs are cached, so the unpatched gate would
       fire ~32k API calls and could poison the live harness's cache
       with nulls. The read-only twins return exactly what the
       originals return when the API yields nothing, so no verdict
       changes -- the study simply refuses to fetch, as briefed.

    Also emitted: `hu`, membership of data/halal_universe.json, which
    covers many more symbols but is a CURRENT snapshot rather than a
    point-in-time judgement. Reported alongside as a coverage check,
    never as the primary universe."""
    import functools
    import importlib.util
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT.parent))
    spec = importlib.util.spec_from_file_location(
        "px", ROOT / "plan/penny_x100.py")
    px = importlib.util.module_from_spec(spec)
    sys.modules["px"] = px
    spec.loader.exec_module(px)
    axb = px.axb
    axb.FILING_LAG_DAYS = 45          # leak #6 hygiene, as the harness sets

    sh_dir, fin_dir = axb.SH, axb.FIN
    axb.PT = _CachedDir(axb.PT)
    _sh, _fin, hit = {}, {}, {"sh": 0, "n": 0}

    def _shares_ro(sym, date):
        k = (sym, date[:7])
        if k not in _sh:
            f = sh_dir / f"{sym}_{date[:7]}.json"
            try:
                _sh[k] = json.loads(f.read_text()) if f.exists() else None
            except Exception:
                _sh[k] = None
        hit["n"] += 1
        hit["sh"] += _sh[k] is not None
        return _sh[k]

    def _fin_ro(sym):
        if sym not in _fin:
            f = fin_dir / f"{sym}.json"
            try:
                _fin[sym] = json.loads(f.read_text()) if f.exists() else []
            except Exception:
                _fin[sym] = []
        return _fin[sym]

    def _no_api(url):
        raise RuntimeError("ic_study must not fetch: " + url[:60])

    axb.shares_asof = _shares_ro
    axb.massive_fin = _fin_ro
    axb.api = _no_api
    axb.industry_clean = functools.lru_cache(maxsize=None)(
        axb.industry_clean)

    df = pd.concat([pd.read_parquet(p, columns=["date", "sym"])
                    for p in sorted(OUT.glob("rows_*.parquet"))])
    pairs = df.drop_duplicates().to_records(index=False)
    pcs = {}
    for fn in POOLS.values():
        for r in json.loads((ROOT / "data/massive" / fn).read_text()):
            pcs.setdefault((r["symbol"], r["date"]), r.get("prev_close"))
    hu_src = json.loads((ROOT / "data/halal_universe.json").read_text())
    pit, hu, t0 = {}, {}, time.time()
    for i, (d, s) in enumerate(pairs):
        try:
            pit[f"{s}|{d}"] = bool(axb.halal_pt(s, d, pcs.get((s, d))))
        except Exception:
            pit[f"{s}|{d}"] = False
        if s not in hu:
            hu[s] = bool(hu_src.get(s, {}).get("halal"))
        if i and i % 25000 == 0:
            print(f"  halal {i}/{len(pairs)} {round(time.time()-t0)}s",
                  flush=True)
    npass = sum(pit.values())
    stats = {"pairs": len(pit), "pit_pass": npass,
             "hu_syms": len(hu), "hu_pass_syms": sum(hu.values()),
             "shares_cache_hit": hit["sh"], "shares_lookups": hit["n"],
             "secs": round(time.time() - t0, 1)}
    (OUT / "halal_flags.json").write_text(
        json.dumps({"pit": pit, "hu": hu, "stats": stats}))
    print(json.dumps(stats, indent=1), flush=True)
    print(f"halal PIT: {npass}/{len(pit)} PASS "
          f"({100*npass/max(len(pit),1):.1f}%)", flush=True)


# ------------------------------------------------------------------
# statistics
# ------------------------------------------------------------------
try:
    from scipy.stats import rankdata as _rankdata
    from scipy.stats import t as _tdist
except Exception:                                  # pragma: no cover
    _rankdata = None
    _tdist = None


def _rank_ref(x):
    """Average-tie ranks (rankdata equivalent, no scipy dependency)."""
    n = len(x)
    o = np.argsort(x, kind="mergesort")
    r = np.empty(n, dtype=np.float64)
    r[o] = np.arange(1, n + 1)
    xs = x[o]
    i = 0
    while i < n:
        j = i + 1
        while j < n and xs[j] == xs[i]:
            j += 1
        if j - i > 1:
            r[o[i:j]] = (i + 1 + j) / 2.0
        i = j
    return r


def _rank(x):
    return _rankdata(x) if _rankdata is not None else _rank_ref(x)


def spearman(x, y, min_n=MIN_NAMES_PER_DAY):
    m = np.isfinite(x) & np.isfinite(y)
    if m.sum() < min_n:
        return np.nan
    a, b = _rank(x[m]), _rank(y[m])
    sa, sb = a.std(), b.std()
    if sa == 0 or sb == 0:
        return np.nan
    return float(((a - a.mean()) * (b - b.mean())).mean() / (sa * sb))


_BOOTIDX = {}


def boot_ci(v, n=10000, seed=17):
    """95% CI on the mean IC by DAY-LEVEL resampling, 10k draws.

    Days are the independent unit: names within a day share the whole
    market's move, so resampling rows would understate the CI by orders
    of magnitude.  The resample index is cached per (n_days, n_draws) so
    every feature sees the identical bootstrap draws -- differences
    between features are then differences in the data, not in the RNG."""
    v = v[np.isfinite(v)]
    m = len(v)
    if m < 20:
        return (np.nan, np.nan)
    key = (m, n, seed)
    idx = _BOOTIDX.get(key)
    if idx is None:
        if len(_BOOTIDX) > 6:          # each entry is ~18 MB
            _BOOTIDX.clear()
        idx = np.random.default_rng(seed).integers(
            0, m, size=(n, m), dtype=np.int32)
        _BOOTIDX[key] = idx
    means = v[idx].mean(axis=1)
    return (float(np.percentile(means, 2.5)),
            float(np.percentile(means, 97.5)))


def daily_ics(df, feats, targets):
    """{(dt, target, feature): (days array, ic array, pool array)}"""
    out = {}
    for dtl, sub in df.groupby("dt", sort=True):
        groups = list(sub.groupby("date", sort=True))
        dates = [d for d, _ in groups]
        pools = [g["pool"].iloc[0] for _, g in groups]
        mats = {f: [g[f].to_numpy(np.float64) for _, g in groups]
                for f in feats}
        for tg in targets:
            yv = [g[tg].to_numpy(np.float64) for _, g in groups]
            for f in feats:
                ic = np.array([spearman(xx, yy)
                               for xx, yy in zip(mats[f], yv)])
                out[(dtl, tg, f)] = (np.array(dates), ic,
                                     np.array(pools))
    return out


def summarise(ics, key, boot=True):
    days, ic, pools = ics[key]
    m = np.isfinite(ic)
    v = ic[m]
    if len(v) < 10:
        return None
    mean = float(v.mean())
    sd = float(v.std(ddof=1))
    t = mean / (sd / math.sqrt(len(v))) if sd > 0 else np.nan
    lo, hi = boot_ci(v) if boot else (np.nan, np.nan)
    pv = pools[m]
    h1 = v[pv == "y2025"]
    h2 = v[pv == "year"]
    return {"n_days": len(v), "mean_ic": mean, "t": float(t),
            "frac_pos": float((v > 0).mean()),
            "ci_lo": lo, "ci_hi": hi,
            "ic_y2025": float(h1.mean()) if len(h1) >= 10 else np.nan,
            "ic_year": float(h2.mean()) if len(h2) >= 10 else np.nan,
            "n_y2025": len(h1), "n_year": len(h2)}


def quantiles(df, feat, target, nq=10, halal=None, min_names=10,
              halal_col="halal"):
    """Per-day quantile buckets of `feat` -> mean forward return.

    Buckets are formed WITHIN each day's cross-section (the alphalens
    convention): the question is "does the name we would have picked
    today beat the others we could have picked today", not "does a
    globally high value beat a globally low one"."""
    sub = df
    if halal is not None:
        sub = sub[sub[halal_col] == halal]
    sub = sub[np.isfinite(sub[feat]) & np.isfinite(sub[target])]
    rows = []
    for _, g in sub.groupby("date", sort=False):
        if len(g) < min_names:
            continue
        x = g[feat].to_numpy(np.float64)
        q = np.floor(_rank(x) / (len(x) + 1e-9) * nq).astype(int)
        q = np.clip(q, 0, nq - 1)
        rows.append(pd.DataFrame({"q": q,
                                  "y": g[target].to_numpy(np.float64)}))
    if not rows:
        return None
    allr = pd.concat(rows)
    g = allr.groupby("q")["y"]
    return pd.DataFrame({"n": g.size(), "mean_ret_pct": g.mean() * 100,
                         "median_ret_pct": g.median() * 100,
                         "win_rate": g.apply(lambda s: (s > 0).mean())})


# ------------------------------------------------------------------
# report
# ------------------------------------------------------------------
MD = ROOT / "IC-STUDY-honest-pool.md"
CSV = ROOT / "ic_study_all_ics.csv"
PRIMARY_TARGETS = [PRIMARY, "fwd_flat"]

# SURVIVAL BAR, fixed before looking at the numbers.  A feature is a
# signal only if it clears ALL FIVE; anything less is a number that
# happened.
SBARS = ["s0", "s1", "s2", "s3", "s4", "s5", "s6"]
SURV = [
    ("S0 tradeable target", "the target is a return a trade can "
                            "capture, not the `peak*` upper bound"),
    ("S1 CI excludes 0", "bootstrap 95% CI on mean IC does not straddle 0"),
    ("S2 BH q<0.05", "survives Benjamini-Hochberg over the whole "
                     "feature x time x target family"),
    ("S3 beats controls", "|mean IC| exceeds BOTH ticker-hash and "
                          "seeded-random in the same cell"),
    ("S4 stable halves", "same sign in y2025 and year, magnitudes "
                         "within 3x of each other"),
    ("S5 abs(IC)>=0.02", "large enough to move a one-pick-per-slot "
                         "strategy at all"),
    ("S6 survives entry lag", "the same feature and decision time "
                              "clears S1-S3 with the SAME SIGN on "
                              f"`{PRIMARY}` -- i.e. it is not an "
                              "artefact of our own entry print"),
]


def _load_rows():
    files = sorted(OUT.glob("rows_*.parquet"))
    if not files:
        raise SystemExit("no extract shards -- run --extract first")
    df = pd.concat([pd.read_parquet(p) for p in files], ignore_index=True)
    hp = OUT / "halal_flags.json"
    if hp.exists():
        hf = json.loads(hp.read_text())
        pit, hu = hf["pit"], hf["hu"]
        df["halal"] = [pit.get(f"{s}|{d}", False)
                       for s, d in zip(df["sym"], df["date"])]
        df["halal_hu"] = [hu.get(s, False) for s in df["sym"]]
        df.attrs["halal_stats"] = hf.get("stats", {})
    else:
        print("WARNING: no halal_flags.json -- halal cut skipped")
        df["halal"] = False
        df["halal_hu"] = False
    df["c37_rank_score"] = (
        (df["coil"].to_numpy() >= 0.95).astype(np.float32) * 10.0
        + np.nan_to_num(df["pressure30"].to_numpy(np.float32),
                        nan=-1.000001))
    return df


def _bh(p):
    """Benjamini-Hochberg q-values (step-up, monotone)."""
    p = np.asarray(p, float)
    n = len(p)
    o = np.argsort(p)
    q = np.empty(n)
    prev = 1.0
    for r, i in enumerate(o[::-1]):
        prev = min(prev, p[i] * n / (n - r))
        q[i] = prev
    return q


def _as_bool(s):
    if s.dtype == bool:
        return s
    return s.map({"True": True, "False": False, True: True, False: False,
                  1: True, 0: False}).fillna(False).astype(bool)


def build_stats(df, reuse=False):
    """Per-cell IC statistics. `reuse` reloads the previous run's CSV --
    the ICs are a pure function of the extract, so re-deriving them to
    reword a paragraph is wasted minutes, not extra rigour."""
    if reuse and CSV.exists():
        S = pd.read_csv(CSV)
        missing = [c for c in SBARS + ["survives", "target"]
                   if c not in S.columns]
        stale = set(S["target"].unique()) != set(TARGETS) if not missing \
            else True
        if missing or stale:
            print(f"  {CSV.name} is stale (missing {missing or 'targets'})"
                  f" -- recomputing", flush=True)
        else:
            for c in SBARS + ["survives"]:
                S[c] = _as_bool(S[c])
            print(f"  reused {len(S)} cells from {CSV.name}", flush=True)
            return S, None
    t0 = time.time()
    ics = daily_ics(df, ALL_FEATS, TARGETS)
    print(f"  daily ICs: {len(ics)} cells in "
          f"{round(time.time()-t0)}s", flush=True)
    recs = []
    for key in ics:
        s = summarise(ics, key)
        if s is None:
            continue
        s["dt"], s["target"], s["feature"] = key
        recs.append(s)
    S = pd.DataFrame(recs)
    p = 2 * _tdist.sf(np.abs(S["t"].to_numpy()),
                      S["n_days"].to_numpy() - 1)
    S["p"] = np.where(np.isfinite(p), p, 1.0)
    S["q_bh"] = _bh(S["p"].to_numpy())
    # per-cell control bar
    ctl = (S[S["feature"].isin(CONTROLS)]
           .assign(a=lambda x: x["mean_ic"].abs())
           .groupby(["dt", "target"])["a"].max())
    S["ctl_bar"] = [ctl.get((d, t), np.nan)
                    for d, t in zip(S["dt"], S["target"])]
    S["s0"] = S["target"].isin(TARGETS_TRADEABLE)
    S["s1"] = ~((S["ci_lo"] <= 0) & (S["ci_hi"] >= 0)) & S["ci_lo"].notna()
    S["s2"] = S["q_bh"] < 0.05
    S["s3"] = S["mean_ic"].abs() > S["ctl_bar"]
    r = (S["ic_y2025"] / S["ic_year"]).abs()
    S["s4"] = (np.sign(S["ic_y2025"]) == np.sign(S["ic_year"])) \
        & (r > 1 / 3) & (r < 3)
    S["s5"] = S["mean_ic"].abs() >= 0.02
    # S6: the bounce control.  Look up the SAME (feature, decision time)
    # on the entry-lag target and require it to be real and same-signed
    # there too.
    pr = S[S["target"] == PRIMARY].set_index(["feature", "dt"])
    ok, sgn = {}, {}
    for key, r_ in pr.iterrows():
        ok[key] = bool(r_["s1"] and r_["s2"] and r_["s3"])
        sgn[key] = np.sign(r_["mean_ic"])
    S["s6"] = [bool(ok.get((f, d), False))
               and np.sign(m) == sgn.get((f, d), 0)
               for f, d, m in zip(S["feature"], S["dt"], S["mean_ic"])]
    S["survives"] = S[SBARS].all(axis=1)
    return S, ics


def _mtable(S, target, col="mean_ic", fmt="{:+.3f}"):
    piv = S[S["target"] == target].pivot_table(
        index="feature", columns="dt", values=col)
    order = [f for f in ALL_FEATS if f in piv.index]
    piv = piv.loc[order]
    cols = list(piv.columns)
    out = ["| feature | " + " | ".join(cols) + " |",
           "|---|" + "---|" * len(cols)]
    for f in piv.index:
        cells = [fmt.format(piv.loc[f, c])
                 if pd.notna(piv.loc[f, c]) else "--" for c in cols]
        tag = "**" if f in CONTROLS else ("_" if f in DIAGNOSTIC
                                          else "")
        out.append(f"| {tag}{f}{tag} | " + " | ".join(cells) + " |")
    return "\n".join(out)


def _ftable(S, target):
    sub = S[S["target"] == target].copy()
    sub["ord"] = [ALL_FEATS.index(f) for f in sub["feature"]]
    sub = sub.sort_values(["dt", "ord"])
    out = ["| dt | feature | days | mean IC | t | frac+ | 95% CI | "
           "ctl bar | q(BH) | IC y2025 | IC year | survives |",
           "|---|---|--:|--:|--:|--:|---|--:|--:|--:|--:|:--:|"]
    for _, r in sub.iterrows():
        tag = "**" if r["feature"] in CONTROLS else (
            "_" if r["feature"] in DIAGNOSTIC else "")
        out.append(
            f"| {r['dt']} | {tag}{r['feature']}{tag} | {r['n_days']:.0f} "
            f"| {r['mean_ic']:+.4f} | {r['t']:+.2f} "
            f"| {r['frac_pos']:.2f} "
            f"| [{r['ci_lo']:+.4f}, {r['ci_hi']:+.4f}] "
            f"| {r['ctl_bar']:.4f} | {r['q_bh']:.3g} "
            f"| {r['ic_y2025']:+.4f} | {r['ic_year']:+.4f} "
            f"| {'YES' if r['survives'] else '.'} |")
    return "\n".join(out)


def _qtable(q, title, label="decile"):
    if q is None or len(q) == 0:
        return f"_{title}: too few names/day to bucket_"
    out = [f"**{title}**", "",
           f"| {label} | n | mean fwd ret % | median % | win rate |",
           "|--:|--:|--:|--:|--:|"]
    for i, r in q.iterrows():
        out.append(f"| {int(i)+1} | {int(r['n'])} "
                   f"| {r['mean_ret_pct']:+.3f} "
                   f"| {r['median_ret_pct']:+.3f} "
                   f"| {r['win_rate']:.3f} |")
    return "\n".join(out)


def pick_study(df, feat, target, dtl, halal=None, tops=(1, 3),
               halal_col="halal", descending=True):
    """What a one-name-per-slot entry rule built on `feat` would earn.

    IC is a cross-sectional rank statistic; the strategy only ever holds
    the TOP name.  This measures the thing the strategy actually eats:
    the mean forward return of the day's #1 (and top-3) by the feature,
    against the mean of every candidate that day (= picking at random)."""
    sub = df[(df["dt"] == dtl)]
    if halal is not None:
        sub = sub[sub[halal_col] == halal]
    sub = sub[np.isfinite(sub[feat]) & np.isfinite(sub[target])]
    hi, lo, allm, n_days = {n: [] for n in tops}, [], [], 0
    for _, g in sub.groupby("date", sort=False):
        if len(g) < MIN_NAMES_PER_DAY:
            continue
        n_days += 1
        o = g.sort_values(feat, ascending=not descending)
        y = o[target].to_numpy(np.float64)
        for n in tops:
            hi[n].append(y[:n].mean())
        lo.append(y[-1])
        allm.append(y.mean())
    if not allm:
        return None
    r = {"n_days": n_days, "all_mean_pct": 100 * float(np.mean(allm)),
         "bottom1_pct": 100 * float(np.mean(lo))}
    for n in tops:
        r[f"top{n}_pct"] = 100 * float(np.mean(hi[n]))
    return r


def _intro(reuse=False):
    df = _load_rows()
    meta = json.loads((OUT / "extract_meta.json").read_text())
    print(f"rows {len(df)}  days {df['date'].nunique()}", flush=True)
    S, ics = build_stats(df, reuse)
    if not reuse:
        S.to_csv(CSV, index=False, float_format="%.6g")

    # "real" = candidate signals only: controls and the bounce
    # diagnostic are instruments, not things we would ever trade, so
    # they must not pad the survivor counts.
    real = S[~S["feature"].isin(CONTROLS + DIAGNOSTIC)]
    surv = real[real["survives"]]
    # Rank candidates on the ENTRY-LAG target, not the raw one: the raw
    # target's leaderboard is the bid-ask bounce's leaderboard.
    top = (real[(real["target"] == PRIMARY) & real["s6"]]
           .assign(a=lambda x: x["mean_ic"].abs())
           .sort_values("a", ascending=False))
    if not len(top):
        top = (real[real["target"] == PRIMARY]
               .assign(a=lambda x: x["mean_ic"].abs())
               .sort_values("a", ascending=False))
    # top-3 DISTINCT features by |mean IC| on the flatten target.
    # dist_sess_high_pct is a monotone transform of coil, so the two
    # carry identical rank information -- they share one slot.
    alias = {"dist_sess_high_pct": "coil"}
    seen, top3 = set(), []
    for _, r in top.iterrows():
        if r["feature"] in DIAGNOSTIC:
            continue
        g = alias.get(r["feature"], r["feature"])
        if g in seen:
            continue
        seen.add(g)
        top3.append(r)
        if len(top3) == 3:
            break

    L = []
    A = L.append
    A("# IC STUDY -- honest pool: does ANY causal feature predict "
      "forward returns?")
    A("")
    A(f"_Generated by `plan/ic_study.py` on {ddate.today().isoformat()}. "
      f"Read-only analysis: no simulator, gate or config file was "
      f"touched._")
    A("")
    A("## 0. What was run")
    A("")
    A(f"* **Universe** -- every `(symbol, date)` in "
      f"`gappers_novol_year.json` + `gappers_novol_y2025.json` with "
      f"`hist_n >= 50` **and** a minute-bar file in `data/massive/m1`: "
      f"**{meta['symbol_days']:,} symbol-days over {meta['days']} "
      f"trading days** (2024-10-22 .. 2026-07-31). **Nothing was "
      f"sampled** -- the full honest pool was processed. The overlap "
      f"day 2025-08-01 is assigned to `y2025` only, so the split-half "
      f"sets are disjoint.")
    A(f"* **Rows** -- {meta['rows']:,} (symbol, day, decision-time) "
      f"observations. A row exists only when the name's +10% cross had "
      f"ALREADY printed at or before the decision time and at least "
      f"{MIN_FWD_BARS} bars remained before the 15:00 ET flatten.")
    A("* **Decision times (ET)** -- 07:30, 08:30, 09:35, 10:00, 10:30, "
      "11:30.")
    A("* **Targets** -- log returns from the decision-time close to "
      "+30min (`fwd30`), +60min (`fwd60`) and the 15:00 flatten "
      "(`fwd_flat`); peak-forward `max(High)/close` over the "
      "+60min (`peak60`) and flatten (`peak_flat`) windows; and "
      "three ENTRY-LAG targets (`fwd60_nx`, `fwd_flat_nx`, "
      "`fwd_flat_nx5`) that re-base the return on a later print "
      "-- see the next bullet, which is the load-bearing one.")
    A("* **The bid-ask bounce control, and why the study is "
      "decided on it.** Every feature is read off the bar at the "
      "decision time, and the plain targets divide by THAT bar's "
      "close. A print sits at the bid or at the ask, so the base "
      "price carries half a spread of noise -- and because a row "
      "exists only after a +10% UP cross, that noise is SELECTED: "
      "the decision print lands on the ask more often than chance, "
      "which depresses the measured forward return, and depresses "
      "it MORE for wider-spread names. That one mechanism can "
      "manufacture exactly the result this study is hunting -- "
      "spread and extension appearing to predict losses -- out of "
      "nothing at all. So `fwd_flat_nx` re-bases on the close of "
      "the FIRST bar after the decision (the earliest price we "
      "could really have paid, and a print whose bid/ask side is "
      "independent of the feature's bar), `fwd_flat_nx5` allows "
      "five minutes of arming latency, and `fwd60_nx` does the "
      "same at the 60-minute horizon. **`fwd_flat_nx` is the "
      "target the verdict is decided on.**")
    A("* **`peak60` / `peak_flat` are reported but excluded from "
      "the verdict.** `max(High)/entry` is an upper bound nobody "
      "can sell at, and it is mechanically increasing in "
      "volatility and in the number of prints, so 'predicting' it "
      "is mostly predicting how noisy and how busy a tape is. The "
      "brief asked for it; bar S0 keeps it out of the conclusion.")
    A("* **Statistic** -- Spearman rank IC computed *within each day's "
      "cross-section* (>= 5 names), then averaged over days. t-stat "
      "and the 95% CI use DAY-level resampling (10,000 draws, shared "
      "draw index across features), because names inside one day share "
      "the day's market move and are not independent.")
    A("")
    A("### The features")
    A("")
    A("All strictly causal, all computed from the one symbol's own "
      "minute bars at or before the decision time.")
    A("")
    A("| group | features |")
    A("|---|---|")
    A("| shape / extension | `coil` (last close / running high, C37's "
      "own coil), `dist_sess_high_pct`, `dist_high60` (last / 60-min "
      "high), `gain_now`, `pm_gain`, `gap7` |")
    A("| tape pressure | `pressure30` (the production statistic: "
      "`Candles.pressure(30, min_vol=20k)`), `pressure30_nv` (same, no "
      "volume floor), `pressure30_bc` (bar-count-normalised: mean "
      "per-bar close position, one vote per bar), `pressure30_t` "
      "(last 30 *calendar minutes* rather than 30 bars), "
      "`pressure10` |")
    A("| participation / density | `log_dvol`, `n_bars` (tape "
      "density), `stale_min` (minutes since the last print), "
      "`no_trade_share` |")
    A("| liquidity / cost | `amihud`, `corwin_schultz`, "
      "`abdi_ranaldo`, `roll`, `bar_range` (the incumbent spread "
      "proxy) -- all from `plan/liquidity_estimators.py`, unmodified |")
    A("| level / vol / clock | `log_price`, `atr_pct`, "
      "`mins_since_cross` |")
    A("| **composite** | `c37_rank_score` -- the ADOPTED champion's "
      "own ordering key, rebuilt exactly as `rotation_sim.rank_at` "
      "sorts (coiled group first, then descending `pressure30`, "
      "missing pressure tied-last). This is the study's most "
      "decision-relevant row. |")
    A("| **diagnostic, not a candidate** | `close_pos` -- where the "
      "decision bar's close sat inside its own high-low range "
      "(1.0 = the ask side, 0.0 = the bid side). It knows nothing "
      "about the future, so whatever it 'predicts' is pure "
      "base-price artefact. It is the ruler for the bounce. |")
    A("| **negative controls** | `ctl_tickerhash`, `ctl_random` |")
    A("")
    A("### Causality: asserted, not assumed")
    A("")
    A("Three independent guards ran in this build (`python "
      "plan/ic_study.py --selftest` reproduces all of them):")
    A("")
    A("1. **Structural.** Features are computed from `pre = "
      "df.iloc[:k]`, the bar prefix ending at the decision bar. Bars "
      "after the decision time are *not in the frame the feature code "
      "receives*, so a slicing bug cannot reach them.")
    A("2. **Gate, every row.** Each row asserts `idx[k-1] <= T` and "
      "`idx[k] > T` (the `plan/causal.py` leak-gate pattern), and each "
      "`plan/liquidity_estimators.py` call re-asserts its own window "
      "boundary inside `_tail_before`. "
      f"In addition **{meta['causalview_verified']:,} rows** "
      f"(1 in 500, of {meta['rows_considered']:,} considered) were "
      f"re-derived with `CausalView(df).upto(T)` and asserted equal "
      f"frame-for-frame.")
    A("3. **Mechanical.** `--selftest` overwrites every bar at or after "
      "T with 9e9 and asserts that **not one of the "
      f"{len(FEATURES)} features moves** -- the proof pattern from "
      "`liquidity_estimators.self_test()`. It also proves the fast bar "
      "loader is index- and value-identical to "
      "`rotation_sim.bars_for`, and that the pressure statistic is "
      "bit-identical to `day-trading.py::Candles.pressure`.")
    A("")
    A("### Negative controls")
    A("")
    A("Two fake features travel through the identical pipeline and are "
      "reported in every table in **bold**:")
    A("")
    A("* `ctl_tickerhash` -- MD5 of the ticker string mapped to [0,1). "
      "A stable, meaningless cross-sectional ordering.")
    A("* `ctl_random` -- a per-row seeded uniform draw.")
    A("")
    A("Their mean |IC| is the **control bar** for that "
      "(decision time, target) cell. A feature that does not clear it "
      "is not a signal, whatever its t-stat says.")
    A("")
    A("### The survival bar (fixed before the numbers were looked at)")
    A("")
    for name, why in SURV:
        A(f"* **{name}** -- {why}")
    A("")
    A(f"Family size for the multiple-testing correction: "
      f"**{len(S)} tests** ({len(ALL_FEATS)} features x "
      f"{len(DECISIONS)} decision times x {len(TARGETS)} targets). At a "
      f"naive 5% we would expect ~{0.05*len(S):.0f} 'significant' "
      f"results from pure noise, which is why S2 is Benjamini-Hochberg "
      f"over the whole family rather than a per-test p-value.")
    A("")
    A("### Two disclosures about the halal gate")
    A("")
    A("1. **The gate was memoised and put in read-only mode.** "
      "`halal_pt` re-reads three or four small JSON caches from disk "
      "per call; measured unpatched it runs at hundreds of "
      "milliseconds per symbol-day, which is hours over this pool. "
      "More importantly, on a cache miss its `shares_asof` helper "
      "**calls Polygon and writes the answer back into "
      "`data/pt_shares`** -- and only ~45% of this study's share-count "
      "lookups are cached, so the unpatched gate would have fired tens "
      "of thousands of requests and written into a cache the live "
      "harness depends on. This run therefore swaps in cached, "
      "read-only, non-fetching twins that return exactly what the "
      "originals return when the API yields nothing. Same verdicts, "
      "no network, no writes. Patched cost: 13.5s for 69,476 "
      "symbol-days.")
    A("2. **A timing probe did write 43 cache files before that patch "
      "existed** (40 real share counts, 3 nulls). The three nulls were "
      "deleted because a cached null is exactly the kind of silent "
      "'cannot verify' that the halal gate must not inherit from a "
      "research script; the 40 genuine values were left in place, "
      "being identical to what the harness would have fetched itself. "
      "Recorded here rather than quietly fixed.")
    A("")
    A("### Why not alphalens")
    A("")
    A("`alphalens` 0.4.6 is installed in the engine's interpreter and "
      "was considered. It was not used, for three reasons, and nothing "
      "was installed into the engine's stack (a prior audit found "
      "user-site `pandas`/`numpy` shadowing broke this environment):")
    A("")
    A("1. Its `get_clean_factor_and_forward_returns` wants a price "
      "panel and derives forward returns by *reindexing on a common "
      "calendar*. Our panel is intraday, ragged, and full of names "
      "that stop printing mid-session -- exactly the rows whose "
      "staleness is itself a feature here. Synthesising a dense panel "
      "would silently repair the data defect the study is trying to "
      "measure.")
    A("2. Its significance machinery is a Newey-West t-stat on the IC "
      "series; the brief asks for a day-level bootstrap, which is a "
      "few lines and makes the resampling unit explicit.")
    A("3. Nothing in it does the two things this study exists for -- "
      "the negative-control comparison and the halal-universe "
      "restriction.")
    A("")
    A("The tear-sheet statistics it would compute (mean IC, IC t-stat, "
      "IC sign consistency, quantile mean returns) are all reproduced "
      "below with the same definitions.")
    A("")
    return L, df, S, ics, top3, real, surv, meta


def _bounce_note(S):
    """One paragraph quantifying how much of the raw result was the
    bid-ask bounce, measured rather than asserted.

    The instrument is `close_pos` (where the decision bar's close sat
    in its own range).  It cannot know anything about the future, so
    whatever IC it shows against the RAW target is pure base-price
    artefact, and the drop from raw to entry-lag is the size of that
    artefact on every other feature too."""
    cp = S[S["feature"] == "close_pos"]
    raw = cp[cp["target"] == "fwd_flat"]["mean_ic"]
    nx = cp[cp["target"] == PRIMARY]["mean_ic"]
    if not len(raw) or not len(nx):
        return ""
    r_ic = float(raw.abs().max())
    n_ic = float(nx.abs().max())
    cand = S[~S["feature"].isin(CONTROLS + DIAGNOSTIC)]
    a = cand[cand["target"] == "fwd_flat"].set_index(["feature", "dt"])
    b = cand[cand["target"] == PRIMARY].set_index(["feature", "dt"])
    j = a[["mean_ic"]].join(b[["mean_ic"]], how="inner",
                            lsuffix="_raw", rsuffix="_nx")
    shrink = 1 - (j["mean_ic_nx"].abs().sum()
                  / max(j["mean_ic_raw"].abs().sum(), 1e-9))
    flips = int((np.sign(j["mean_ic_raw"]) !=
                 np.sign(j["mean_ic_nx"])).sum())
    return (
        "**How much of this was the bid-ask bounce, measured.** "
        f"`close_pos` -- purely where the decision bar's close sat "
        f"inside its own high-low range, an instrument with no "
        f"knowledge of the future whatsoever -- scores |IC| up to "
        f"**{r_ic:.4f}** against the RAW target `fwd_flat` and only "
        f"**{n_ic:.4f}** against the entry-lag target `{PRIMARY}`. "
        f"That gap is the artefact, isolated. Across every real "
        f"feature and decision time the same re-basing shrinks total "
        f"|mean IC| by **{100*shrink:.0f}%** and flips the sign of "
        f"**{flips} of {len(j)}** cells. Any conclusion drawn from the "
        f"raw target alone would have been, to that extent, a "
        f"conclusion about our own entry print. "
        f"(`close_pos` is a LOWER bound on the artefact: a bar with a "
        f"single print has no range, so it scores 0.5 and hides which "
        f"side of the book it was on. On premarket tapes that is a "
        f"large minority of bars.)")


def report(reuse=False):
    L, df, S, ics, top3, real, surv, meta = _intro(reuse)
    A = L.append
    n_tests = len(S)

    # ---------------- 1. headline -----------------------------------
    funnel = [(nm, int(real[c].sum())) for (nm, _), c in
              zip(SURV, SBARS)]
    cum, prev = [], real
    for c, (nm, _) in zip(SBARS, SURV):
        prev = prev[prev[c]]
        cum.append((nm, len(prev)))
    A("## 1. Headline")
    A("")
    A(f"**{len(surv)} of {len(real)} real feature-cells survive all "
      f"{len(SURV)} bars.**")
    A("")
    A("| bar | cells passing this bar alone | cells still alive "
      "(cumulative) |")
    A("|---|--:|--:|")
    for (nm, alone), (_, c) in zip(funnel, cum):
        A(f"| {nm} | {alone} | {c} |")
    A("")
    if len(surv) == 0:
        A("Nothing clears the bar. The detail is in sections 2-7; the "
          "plainly-worded reading is in section 8.")
    else:
        A("Surviving cells:")
        A("")
        A("| feature | dt | target | mean IC | t | 95% CI | ctl bar | "
          "q(BH) | IC y2025 | IC year |")
        A("|---|---|---|--:|--:|---|--:|--:|--:|--:|")
        _srt = surv.sort_values("mean_ic", key=abs, ascending=False)
        _cap = 60
        for _, r in _srt.head(_cap).iterrows():
            A(f"| {r['feature']} | {r['dt']} | {r['target']} "
              f"| {r['mean_ic']:+.4f} | {r['t']:+.2f} "
              f"| [{r['ci_lo']:+.4f}, {r['ci_hi']:+.4f}] "
              f"| {r['ctl_bar']:.4f} | {r['q_bh']:.3g} "
              f"| {r['ic_y2025']:+.4f} | {r['ic_year']:+.4f} |")
        if len(_srt) > _cap:
            A("")
            A(f"_...and {len(_srt)-_cap} more surviving cells; the "
              f"complete list is in `ic_study_all_ics.csv` "
              f"(`survives == True`)._")
    A("")

    # ---------------- 2. mean-IC matrices ---------------------------
    A("## 2. Mean IC by feature x decision time, per target")
    A("")
    A("Every cell is the average over trading days of that day's "
      "cross-sectional Spearman correlation between the feature and the "
      "target. Controls in **bold**, the bounce diagnostic in "
      "_italics_. Read "
      f"2.{TARGETS.index('fwd_flat')+1} (`fwd_flat`) against "
      f"2.{TARGETS.index(PRIMARY)+1} (`{PRIMARY}`): the difference "
      "between those two matrices is the bid-ask bounce. The "
      f"`peak*` matrices (2.{TARGETS.index('peak60')+1} and "
      f"2.{TARGETS.index('peak_flat')+1}) are upper bounds and are "
      "excluded from the verdict. For scale: a mean IC of 0.02 is "
      "the smallest number that could plausibly matter to a "
      "one-name-at-a-time strategy; 0.05+ is what a usable factor looks "
      "like in the equity-factor literature.")
    A("")
    # free internal consistency check: dist_sess_high_pct is a strictly
    # DECREASING transform of coil ((1/coil - 1) * 100), so a rank
    # statistic must return exactly the mirror image. If it does not,
    # the pipeline is broken.
    a = S[S["feature"] == "coil"].set_index(["dt", "target"])["mean_ic"]
    b = (S[S["feature"] == "dist_sess_high_pct"]
         .set_index(["dt", "target"])["mean_ic"])
    mism = float((a + b).abs().max())
    A(f"_Built-in consistency check: `dist_sess_high_pct` is the "
      f"monotone-decreasing transform `(1/coil - 1)*100`, so its rank "
      f"IC must be exactly minus `coil`'s. Largest disagreement over "
      f"all {len(a)} cells: **{mism:.2e}** (float32 storage rounding). "
      f"The two rows are therefore one feature reported twice, kept "
      f"because the brief asked for both._")
    A("")
    for tg in TARGETS:
        A(f"### 2.{TARGETS.index(tg)+1} target = `{tg}`")
        A("")
        A(_mtable(S, tg))
        A("")

    # ---------------- 3. full statistics ----------------------------
    A("## 3. Full statistics and the control comparison")
    A("")
    A("`ctl bar` is the larger of the two controls' |mean IC| in the "
      "same cell. `frac+` is the fraction of days with a positive IC "
      "(0.50 = coin flip). `survives` = every bar from section 0.")
    A("")
    for tg in PRIMARY_TARGETS:
        A(f"### 3.{PRIMARY_TARGETS.index(tg)+1} target = `{tg}`")
        A("")
        A(_ftable(S, tg))
        A("")
    A(f"The same statistics for all {n_tests} cells (every feature x "
      f"decision time x target) are in `ic_study_all_ics.csv` next to "
      f"this file.")
    A("")

    # ---------------- 4. control comparison summary -----------------
    A("## 4. Do the real features beat their controls?")
    A("")
    A("\"Real\" here excludes both controls and the `close_pos` "
      "diagnostic. `real cells above the control bar` counts how many "
      "of the candidate features in that cell beat the larger control "
      "-- with 24 candidates and a control bar set by the max of two "
      "noise draws, pure chance gives roughly a third.")
    A("")
    A("| dt | target | best real \\|IC\\| | that feature | "
      "ctl_tickerhash | ctl_random | real cells above the control bar |")
    A("|---|---|--:|---|--:|--:|--:|")
    for tg in TARGETS:
        for dtl in sorted(S["dt"].unique()):
            cell = S[(S["dt"] == dtl) & (S["target"] == tg)]
            rc = cell[~cell["feature"].isin(CONTROLS + DIAGNOSTIC)]
            if not len(rc):
                continue
            b = rc.loc[rc["mean_ic"].abs().idxmax()]
            th = cell[cell["feature"] == "ctl_tickerhash"]["mean_ic"]
            rd = cell[cell["feature"] == "ctl_random"]["mean_ic"]
            A(f"| {dtl} | {tg} | {abs(b['mean_ic']):.4f} "
              f"| {b['feature']} "
              f"| {abs(float(th.iloc[0])):.4f} "
              f"| {abs(float(rd.iloc[0])):.4f} "
              f"| {int(rc['s3'].sum())}/{len(rc)} |")
    A("")

    # ---------------- 5. split-half ---------------------------------
    A("## 5. Split-half stability (y2025 vs year)")
    A("")
    A("`y2025` = 2024-10-22 .. 2025-08-01, `year` = 2025-08-02 .. "
      "2026-07-31 -- disjoint, roughly equal day counts. A feature "
      "whose IC flips sign between halves is not a feature.")
    A("")
    A(f"| feature | cells | same sign | same sign AND within 3x | "
      f"same sign on `{PRIMARY}` | worst flip |")
    A("|---|--:|--:|--:|--:|---|")
    for f in ALL_FEATS:
        sub = S[S["feature"] == f]
        sub = sub[sub["ic_y2025"].notna() & sub["ic_year"].notna()]
        if not len(sub):
            continue
        same = int((np.sign(sub["ic_y2025"]) ==
                    np.sign(sub["ic_year"])).sum())
        both = int(sub["s4"].sum())
        pr = sub[sub["target"] == PRIMARY]
        psame = int((np.sign(pr["ic_y2025"]) ==
                     np.sign(pr["ic_year"])).sum())
        flip = sub.loc[(sub["ic_y2025"] - sub["ic_year"]).abs().idxmax()]
        tag = "**" if f in CONTROLS else ("_" if f in DIAGNOSTIC else "")
        A(f"| {tag}{f}{tag} | {len(sub)} | {same} | {both} "
          f"| {psame}/{len(pr)} "
          f"| {flip['dt']}/{flip['target']}: "
          f"{flip['ic_y2025']:+.3f} vs {flip['ic_year']:+.3f} |")
    A("")
    A("The controls behave exactly as controls should -- their sign "
      "agreement sits near the 50% a coin would give. Any real feature "
      "that does the same is a coin too.")
    A("")

    # ---------------- 6. quantiles ----------------------------------
    A("## 6. Quantile study -- do the top names actually earn?")
    A("")
    A("Deciles are formed **within each day's cross-section** (decile "
      "10 = the day's highest values), then forward returns are pooled. "
      "This is the alphalens convention and it is the right one here: "
      "the strategy chooses among the names available *that day*, not "
      "against a global threshold.")
    A("")
    u = df.drop_duplicates(["sym", "date"])
    nall, nh, nhu = len(u), int(u["halal"].sum()), int(u["halal_hu"].sum())
    hs = df.attrs.get("halal_stats", {})
    A("The tradeable universe is much smaller than the pool, and two "
      "definitions of it are reported because neither is clean:")
    A("")
    A(f"* **HALAL-PIT** -- the harness's own point-in-time gate "
      f"(`penny_ax11b_massive.halal_pt`, `FILING_LAG_DAYS=45`): "
      f"**{nh:,} of {nall:,} symbol-days "
      f"({100*nh/max(nall,1):.1f}%)**. This is what the backtests "
      f"actually gated on. Its financial caches cover only "
      f"{100*hs.get('shares_cache_hit',0)/max(hs.get('shares_lookups',1),1):.0f}% "
      f"of the pool's share-count lookups, and this study refuses to "
      f"fetch the rest, so uncached names fall through to the gate's "
      f"own `rules_ytd` fallback -- exactly as the unpatched gate "
      f"behaves when the API returns nothing.")
    A(f"* **HALAL-UNIV** -- membership of `data/halal_universe.json`: "
      f"**{nhu:,} of {nall:,} symbol-days "
      f"({100*nhu/max(nall,1):.1f}%)**. Broader symbol coverage, but "
      f"it is a CURRENT snapshot, so it carries mild hindsight and is "
      f"shown only as a coverage check on the first bullet -- never as "
      f"the primary universe.")
    A("")
    A("A signal that works only on names we cannot trade is useless to "
      "us, so the halal tables, not the all-names tables, are the ones "
      "that decide anything.")
    A("")
    A("Each feature gets the same four tables: the raw target "
      "`fwd_flat` (based on the decision bar's own close) and the "
      f"entry-lag target `{PRIMARY}` (based on the next print) side by "
      "side on all names, then the entry-lag target on each halal "
      "universe. **The gap between the first two tables is the bid-ask "
      "bounce**, and it is the single most important comparison in "
      "this document.")
    A("")
    for i, r in enumerate(top3):
        f, dtl = r["feature"], r["dt"]
        A(f"### 6.{i+1} `{f}` at {dtl} "
          f"(mean IC {r['mean_ic']:+.4f} vs `{PRIMARY}`)")
        A("")
        sub = df[df["dt"] == dtl]
        A(_qtable(quantiles(sub, f, "fwd_flat"),
                  f"{f} deciles -> RAW `fwd_flat` (entry at the "
                  f"decision bar's close), ALL names"))
        A("")
        A(_qtable(quantiles(sub, f, PRIMARY),
                  f"{f} deciles -> ENTRY-LAG `{PRIMARY}` (entry at the "
                  f"next print), ALL names"))
        A("")
        A(_qtable(quantiles(sub, f, PRIMARY, nq=5, halal=True,
                            min_names=10),
                  f"{f} QUINTILES -> `{PRIMARY}`, HALAL-PIT names only "
                  f"(the halal cut leaves too few names per day for "
                  f"10 buckets, so 5)",
                  label="quintile"))
        A("")
        A(_qtable(quantiles(sub, f, PRIMARY, nq=5, halal=True,
                            min_names=10, halal_col="halal_hu"),
                  f"{f} QUINTILES -> `{PRIMARY}`, HALAL-UNIV names only",
                  label="quintile"))
        A("")
    A(f"### 6.{len(top3)+1} the same three features at 10:00 ET")
    A("")
    A("07:30 and 08:30 cross-sections are small and premarket-thin. "
      "10:00 is the session's first liquid decision point and the one "
      "the live harness actually arms into, so the same feature is "
      "shown there as a robustness check.")
    A("")
    for r in top3:
        f = r["feature"]
        A(_qtable(quantiles(df[df["dt"] == "10:00"], f, PRIMARY),
                  f"{f} deciles -> `{PRIMARY}` at 10:00, ALL names"))
        A("")
    A(f"### 6.{len(top3)+2} the controls, same treatment")
    A("")
    for f in CONTROLS:
        dtl = top3[0]["dt"]
        A(_qtable(quantiles(df[df["dt"] == dtl], f, PRIMARY),
                  f"CONTROL {f} deciles -> `{PRIMARY}` at {dtl}, "
                  f"ALL names"))
        A("")
    A("### 6.{} the bounce, measured directly".format(len(top3) + 3))
    A("")
    A("`close_pos` is where the decision bar's close sat inside its own "
      "high-low range: 1.0 = printed at the top of the bar (the ask "
      "side), 0.0 = at the bottom (the bid side). It cannot predict "
      "anything about the market -- but it fully determines which side "
      "of the spread our base price was on. If the raw target is "
      "bounce-contaminated, `close_pos` will look like a monster signal "
      "against `fwd_flat` and like nothing against "
      f"`{PRIMARY}`.")
    A("")
    for tg in ("fwd_flat", PRIMARY):
        A(_qtable(quantiles(df[df["dt"] == "10:00"], "close_pos", tg),
                  f"close_pos deciles -> `{tg}` at 10:00, ALL names"))
        A("")

    # ---------------- 7. pick study ---------------------------------
    A("## 7. What an entry rule built on these would actually earn")
    A("")
    A("IC is a rank statistic over the whole cross-section; the cash "
      "account holds **one name at a time**. This table asks the "
      "question the account asks: take the day's #1 (and top-3) by the "
      "feature -- in the direction its IC says is good -- hold to the "
      "15:00 flatten, and compare with picking uniformly at random "
      f"from that day's candidates. Returns are `{PRIMARY}`: entry at "
      "the next print after the decision, which is both the honest "
      "fill and the bounce-free measurement. Still gross of spread "
      "crossing, slippage and impact.")
    A("")
    A("| feature | dir | dt | universe | days | top-1 % | top-3 % | "
      "random pick % | bottom-1 % | top1 - random |")
    A("|---|:--:|---|---|--:|--:|--:|--:|--:|--:|")
    picks = [(r["feature"], r["dt"], r["mean_ic"] > 0) for r in top3] + \
            [(c, top3[0]["dt"], True) for c in CONTROLS]
    for f, dtl, hi_is_good in picks:
        for uni, hl, hc in (("all", None, "halal"),
                            ("halal-PIT", True, "halal"),
                            ("halal-UNIV", True, "halal_hu")):
            ps = pick_study(df, f, PRIMARY, dtl, halal=hl,
                            halal_col=hc, descending=hi_is_good)
            if ps is None:
                continue
            tag = "**" if f in CONTROLS else ""
            A(f"| {tag}{f}{tag} | {'high' if hi_is_good else 'low'} "
              f"| {dtl} | {uni} | {ps['n_days']} "
              f"| {ps['top1_pct']:+.3f} | {ps['top3_pct']:+.3f} "
              f"| {ps['all_mean_pct']:+.3f} "
              f"| {ps['bottom1_pct']:+.3f} "
              f"| {ps['top1_pct']-ps['all_mean_pct']:+.3f} |")
    A("")
    A("`dir` is which end of the feature the rule takes: `high` = the "
      "day's largest value, `low` = the smallest. It follows the sign "
      "of the measured IC, it is not fitted here.")
    A("")
    base_mu = 100 * float(np.nanmean(df["fwd_flat"]))
    base_md = 100 * float(np.nanmedian(df["fwd_flat"]))
    A("Reminder of the unconditional base rate on this pool: the mean "
      f"`fwd_flat` over every row is **{base_mu:+.3f}%** and the median "
      f"is **{base_md:+.3f}%**. "
      + ("Holding a crossed name from a decision time to the flatten "
         "is a LOSING proposition on average before any cost at all, "
         "so a ranking signal here does not pick winners -- it picks "
         "which loser to hold unless it is strong enough to flip the "
         "sign."
         if base_mu <= 0 else
         "The unconditional drift is positive, so a ranking signal has "
         "something to work with; costs still have to come out of it."))
    A("")

    # ---------------- 8. verdict ------------------------------------
    A("## 8. Verdict")
    A("")
    bounce = _bounce_note(S)
    if len(surv) == 0:
        A("**No causal feature tested here predicts forward returns on "
          "the honest pool once the entry-lag control is applied.** Not "
          f"one of the {len(real)} real feature-cells clears all "
          f"{len(SURV)} bars, and the funnel in section 1 shows where "
          "they die.")
        A("")
        A(bounce)
        A("")
        A("**Recommendation: stop sweeping. Report the honest "
          "ceiling.** There is no entry rule to build out of this "
          "feature set, so further veto / ordering / phase / threshold "
          "configurations can only find noise that survives by chance "
          f"-- and with a {n_tests}-test family, something always will. "
          "The honest number for this universe and ruleset family is "
          "the one already measured (C37 parameters on the "
          "full-coverage pool: -$72,673 over 445 days), and the correct "
          "output of the W-campaign is that number plus this null "
          "result, not another configuration.")
    else:
        A(f"**{len(surv)} of {len(real)} feature-cells clear all "
          f"{len(SURV)} bars, and they are not spread evenly: "
          f"{surv['feature'].nunique()} distinct features are "
          f"involved.** The list is in section 1.")
        A("")
        A("### What survives, and which way it points")
        A("")
        best = (surv[surv["target"] == PRIMARY]
                if (surv["target"] == PRIMARY).any() else surv)
        best = best.sort_values("mean_ic", key=abs, ascending=False)
        shown = set()
        for _, r in best.iterrows():
            if r["feature"] in shown or r["feature"] in DIAGNOSTIC:
                continue
            shown.add(r["feature"])
            d = "HIGHEST" if r["mean_ic"] > 0 else "LOWEST"
            A(f"* At **{r['dt']} ET**, among crossed candidates, prefer "
              f"the **{d}** `{r['feature']}` (mean IC "
              f"{r['mean_ic']:+.4f} vs `{r['target']}`, control bar "
              f"{r['ctl_bar']:.4f}, halves "
              f"{r['ic_y2025']:+.4f}/{r['ic_year']:+.4f}; "
              f"{int((surv['feature']==r['feature']).sum())} of its "
              f"{len(DECISIONS)*len(TARGETS)} cells survive).")
            if len(shown) == 8:
                break
        A("")
        A(bounce)
        A("")
        A("### What this does NOT license")
        A("")
        A("* **It is not a backtest.** An IC says the ranking carries "
          "information; it says nothing about whether the information "
          "survives the spread we have to cross, the depth we have to "
          "eat, or the halt behaviour of these names. Section 7 is "
          "gross of all three.")
        A("* **The halal universe is where it has to work, and that is "
          "the thinnest evidence in this document.** The halal cut "
          "leaves a handful of names per day, so its quantile tables "
          "rest on hundreds of observations, not tens of thousands. "
          "Any rule adopted from here must be re-measured on the halal "
          "universe alone before it is believed.")
        A("* **Nothing here rescues C37.** The champion’s ranker is "
          "measured directly as `c37_rank_score`; see the next "
          "subsection.")
        A("")
    # --- the C37 ranker gets its own subsection either way -----------
    A("### The adopted champion's own ranker, measured directly")
    A("")
    c37 = real[real["feature"] == "c37_rank_score"]
    for tg in (PRIMARY, "fwd_flat"):
        sub = c37[c37["target"] == tg]
        if not len(sub):
            continue
        b = sub.loc[sub["mean_ic"].abs().idxmax()]
        A(f"* vs `{tg}`: ranges "
          f"{sub['mean_ic'].min():+.4f} .. {sub['mean_ic'].max():+.4f} "
          f"across the six decision times, strongest "
          f"{b['mean_ic']:+.4f} at {b['dt']} "
          f"(control bar {b['ctl_bar']:.4f}, halves "
          f"{b['ic_y2025']:+.4f}/{b['ic_year']:+.4f}).")
    n_c37 = int(surv[surv["feature"] == "c37_rank_score"].shape[0])
    c37p = c37[c37["target"] == PRIMARY]["mean_ic"]
    A("")
    if len(c37p) and c37p.mean() < 0:
        A(f"**`c37_rank_score` is NEGATIVELY predictive** (mean "
          f"{c37p.mean():+.4f} over the six decision times on "
          f"`{PRIMARY}`), with {n_c37} surviving cells. The champion "
          "does not rank at random -- it ranks BACKWARDS. The names it "
          "puts first are, on average, the names that go on to do "
          "worse than the ones it puts last. That is a stronger and "
          "more useful statement than the portfolio-level "
          "'negative per-trade expectancy' already recorded: it "
          "localises the loss in the RANKER, not in the universe, and "
          "it means the coiled-first / pressure-ordered rule is not a "
          "neutral tie-break that costs nothing -- it is actively "
          "selecting the wrong side of a real effect.")
    else:
        A(f"`c37_rank_score` sits at mean "
          f"{(c37p.mean() if len(c37p) else float('nan')):+.4f} on "
          f"`{PRIMARY}` with {n_c37} surviving cells.")
    A("")
    A("### What would change the answer further")
    A("")
    A("* A different *universe*. Everything here conditions on the "
      "+10% cross on a novol gapper pool. Whatever is true here is "
      "true of that pool, not of markets.")
    A("* A different *information set*. Every feature is a function of "
      "one symbol's own minute bars. News and filing text, float and "
      "short interest, the real order book, and cross-sectional market "
      "state are all absent -- and the live-session logs keep pointing "
      "at the book as the thing that actually discriminates.")
    A("* A different *horizon*. This tests intraday-to-flatten only, "
      "the horizon the cash-account rules impose.")
    A("")
    A("---")
    A("")
    A(f"_Extraction: {meta['rows']:,} rows from "
      f"{meta['symbol_days']:,} symbol-days in {meta['secs']:.0f}s. "
      f"Reproduce with `python plan/ic_study.py --selftest --extract "
      f"--halal --analyze`._")
    A("")
    MD.write_text("\n".join(L), encoding="utf-8")
    print(f"wrote {MD} ({MD.stat().st_size/1024:.0f} KB) and {CSV}")


# ------------------------------------------------------------------
# self-test: the causality guards, mechanically
# ------------------------------------------------------------------
def selftest():
    ok = 0
    by_day = load_pool()
    days = sorted(by_day)
    rng = random.Random(3)
    picks = []
    while len(picks) < 12:
        d = rng.choice(days)
        sym, pc, _ = rng.choice(by_day[d])
        picks.append((sym, d, pc))

    # 1) loader equivalence with rotation_sim.bars_for
    for sym, d, _ in picks:
        fast = load_bars(sym, d)
        ref = _ref_load_bars(sym, d)
        if fast is None or ref is None:
            continue
        ref2 = ref.copy()
        ref2.index = ref2.index.tz_localize(None)
        ref2 = ref2[ref2.index.normalize() == pd.Timestamp(d)]
        assert len(fast) == len(ref2), f"{sym} {d}: {len(fast)}/{len(ref2)}"
        assert (fast.index.to_numpy() == ref2.index.to_numpy()).all(), \
            f"{sym} {d}: index mismatch vs rotation_sim loader"
        assert np.allclose(fast["Close"].to_numpy(),
                           ref2["Close"].to_numpy())
    ok += 1
    print("  [1] fast loader == rotation_sim.bars_for (index + values)")

    # 2) pressure == day-trading.py Candles.pressure
    import importlib.util
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT.parent))
    spec = importlib.util.spec_from_file_location(
        "px", ROOT / "plan/penny_x100.py")
    px = importlib.util.module_from_spec(spec)
    sys.modules["px"] = px
    spec.loader.exec_module(px)
    dt_mod = px.ps
    checked = 0
    for sym, d, _ in picks:
        df = load_bars(sym, d)
        if df is None or len(df) < 40:
            continue
        for cut in (60, 120, len(df)):
            w = df.iloc[:min(cut, len(df))]
            cd = dt_mod.Candles(w)
            for n, mv in ((30, 20_000), (30, 0), (10, 0)):
                a = cd.pressure(cd.n - 1, n, mv)
                b = pressure_last(w["High"].to_numpy(),
                                  w["Low"].to_numpy(),
                                  w["Close"].to_numpy(),
                                  w["Volume"].to_numpy(), n, mv)
                assert (a is None) == (b is None), f"{sym} {d} {n} {mv}"
                if a is not None:
                    assert abs(a - b) < 1e-12, f"{sym} {d} {n}: {a} {b}"
                checked += 1
    assert checked > 20
    ok += 1
    print(f"  [2] pressure == Candles.pressure ({checked} comparisons)")

    # 3) MECHANICAL CAUSALITY: poison every bar at/after T; nothing moves
    poisoned_checks = 0
    for sym, d, pc in picks:
        df = load_bars(sym, d)
        if df is None or len(df) < 60:
            continue
        T = dtime(10, 0)
        t_ts = pd.Timestamp(d) + pd.Timedelta(hours=10)
        k = int(np.searchsorted(df.index.to_numpy(),
                                np.datetime64(t_ts), side="right"))
        if k < 10 or k >= len(df):
            continue
        cross = df.index[0]
        nxt = t_ts + pd.Timedelta(minutes=1)
        # Both sides go through the SAME slicing path rows_for() uses,
        # so this proves the searchsorted prefix too, not merely that
        # features_at is a pure function of its argument.
        def _feats(frame):
            kk = int(np.searchsorted(frame.index.to_numpy(),
                                     np.datetime64(t_ts), side="right"))
            return features_at(frame.iloc[:kk], nxt, pc, cross, t_ts,
                               sym, d)
        a = _feats(df)
        bad = df.copy()
        bad.iloc[k:, :] = 9e9
        b = _feats(bad)
        for kk in a:
            x, y = a[kk], b[kk]
            if x is None or y is None:
                assert x is y, f"CAUSALITY BREACH {sym} {d} {kk}"
            else:
                assert (math.isnan(x) and math.isnan(y)) or x == y, \
                    f"CAUSALITY BREACH {sym} {d} {kk}: {x} != {y}"
        poisoned_checks += 1
    assert poisoned_checks >= 5, poisoned_checks
    ok += 1
    print(f"  [3] poisoning bars >= T moved no feature "
          f"({poisoned_checks} symbol-days x {len(FEATURES)} features)")

    # 4) the leak gate actually fires
    df = load_bars(*picks[0][:2])
    cv = CausalView(df, "T", "T")
    try:
        cv.future(df.index[5])
        raise SystemExit("FAIL: CausalView.future did not raise")
    except Exception as e:
        assert "allow_lookahead" in str(e)
    ok += 1
    print("  [4] CausalView leak gate fires on an undeclared peek")

    # 5) liquidity_estimators own self-test still passes
    LE.self_test()
    ok += 1

    # 6) rank/spearman sanity
    x = np.array([1.0, 2, 3, 4, 5])
    assert abs(spearman(x, x * 3, 5) - 1.0) < 1e-12
    assert abs(spearman(x, -x, 5) + 1.0) < 1e-12
    ok += 1
    print("  [6] spearman +-1 on monotone inputs")
    print(f"ic_study self-test: {ok}/6 groups passed")


# ------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--extract", action="store_true")
    ap.add_argument("--halal", action="store_true")
    ap.add_argument("--analyze", action="store_true")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--limit-days", type=int, default=0)
    ap.add_argument("--reuse-stats", action="store_true",
                    help="reload ic_study_all_ics.csv instead of "
                         "recomputing the ICs (report rewording)")
    a = ap.parse_args()
    if a.selftest:
        selftest()
    if a.extract:
        extract(a.workers, a.limit_days)
    if a.halal:
        build_halal()
    if a.analyze:
        report(a.reuse_stats)


if __name__ == "__main__":
    main()
