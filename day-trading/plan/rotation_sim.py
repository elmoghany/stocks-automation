"""R-campaign Phase 2: SEQUENTIAL TICKET ROTATION simulator.

CASH RULES (user 2026-08-09, hard constraints):
  * ONE position at a time -- ticket N+1 deploys only after ticket N
    has fully exited. Never two open names.
  * Flat $15,000 tickets, final ticket $10,000, up to $100,000/day.

THE IDEA: Z104 marries the whole day to one 7AM pick; every re-entry
returns to the same name. Rotation frees each ticket: when a ticket
exits, the NEXT ticket goes to whichever name ranks best on the
CURRENT 5-minute data (coiled-first, premarket... rather, as-of-now
pressure order). The day becomes up to 7 information-fresh sequential
picks. Fully causal: ranking at time t uses bars <= t only; a name is
eligible only after its +10% crossing has printed.

Reuses day-trading.py::simulate_trades per ticket (max_trades=1,
entry_start=t, Z104 exit machinery, halt_aware, 50bps premarket
spread, causal sizing). Only the FIRST entry group of each call is
consumed; control then returns to the rotation loop at its exit time.

Configs (CFGS): R020 full rotation, R021 rotate-on-loss-only,
R023 no-rotation baseline (same-name ladder under the flat schedule),
R024 top-3 restriction, R025/R026 stale-pick escape, R028 late-entry
window sweep, R029 afternoon-only control.

Usage: python plan/rotation_sim.py R020 [--days N]  (N=quick smoke)
Results appended to data/massive/rotation_results.json.
"""

import gzip
import importlib.util
import json
import sys
from collections import defaultdict
from datetime import time as dtime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent))
_spec = importlib.util.spec_from_file_location("px", ROOT / "plan/penny_x100.py")
px = importlib.util.module_from_spec(_spec)
sys.modules["px"] = px
_spec.loader.exec_module(px)
dt = px.ps          # day-trading module (loaded by the x100 chain)
axb = px.axb
# Leak #6 hygiene: quarters usable only after their ~45-day filing lag
# (the x100 runs set this per-spec; the wrapper must too). V102 measured
# the direction as NOT inflating, but the standard is zero leaks.
axb.FILING_LAG_DAYS = 45

M1 = ROOT / "data/massive/m1"
# Parallel runs must NOT share one results file -- the read-modify-write
# at the end of run() would clobber siblings. ROTSHARD gives each process
# its own file; merge afterwards.
import os as _os
_SHARD = _os.environ.get("ROTSHARD", "")
RES_F = ROOT / (f"data/massive/rotation_results_{_SHARD}.json" if _SHARD
                else "data/massive/rotation_results.json")
# Feature cache is OPT-IN (FEATCACHE=1). It only ever supplies numbers
# identical to live computation -- prove it with
# `python plan/feature_cache.py --verify` before switching it on.
USE_FEATCACHE = _os.environ.get("FEATCACHE") == "1"
_FC = {}


def _featcache_for(date):
    if date not in _FC:
        try:
            spec = importlib.util.spec_from_file_location(
                "fc", ROOT / "plan/feature_cache.py")
            m = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(m)
            _FC[date] = m.load(date)
        except Exception as e:
            print(f"ERROR: feature cache unavailable ({e}) -- computing "
                  f"live for {date}")
            _FC[date] = None
    return _FC[date]


TICKETS = [15_000.0] * 6 + [10_000.0]          # user schedule: 6x15k + 10k
SCAN_STEP = 5                                   # minutes between re-ranks
EXIT_END = dtime(15, 0)

# Z104's OWN merged sim machinery -- pulled from the registry so the
# rotation ticket trades exactly like the champion (incl. its buy_set
# pattern exclusions). Only capital keys are overridden: budget is
# per-ticket, the daily cap and ticket schedule are enforced by the
# rotation loop itself, and max_trades=1 hands control back after one
# entry+exit.
# NOTE the registry's sim dict holds only OVERRIDES -- the trail/stop/
# scale-out defaults live in px.BASE_SIM and are merged at run time.
# Copying only the overrides ran tickets in legacy cents-mode (caught
# 2026-08-09 by the R023 baseline failing to reproduce the champion).
SIMKW = dict(px.BASE_SIM)
SIMKW.update(px.BYID["Z104"]["sim"])
for _k in ("entry_ticket_schedule", "daily_deploy_cap", "budget"):
    SIMKW.pop(_k, None)
SIMKW.update(verbose=False, max_trades=1, daily_deploy_cap=None)
assert SIMKW.get("trail_pct"), "trail machinery missing -- refuse to run"

CFGS = {
    "R020": dict(desc="full rotation, re-pick every freed ticket"),
    "R021": dict(desc="rotate only after a LOSING ticket", on_win="stay"),
    "R023": dict(desc="no-rotation baseline: same-name ladder, flat "
                      "15k schedule", rotate=False),
    "R024": dict(desc="rotation restricted to current top-3", top=3),
    "R025": dict(desc="R020 + stale-pick escape 09:30",
                 escape=dtime(9, 30)),
    "R026": dict(desc="R020 + stale-pick escape 10:00",
                 escape=dtime(10, 0)),
    "R028a": dict(desc="rotation, last new ticket 13:00",
                  entry_cutoff=dtime(13, 0)),
    "R028b": dict(desc="rotation, last new ticket 14:00",
                  entry_cutoff=dtime(14, 0)),
    "R029": dict(desc="CONTROL afternoon-only rotation 12:00-15:00",
                 entry_open=dtime(12, 0), entry_cutoff=dtime(14, 0)),
    # ---- Phase 4: the stack and its deciders ----
    "R060": dict(desc="STACK: rotation + 14:00 window + 10:00 escape",
                 entry_cutoff=dtime(14, 0), escape=dtime(10, 0)),
    "R061": dict(desc="stack adjacency: window 14:30",
                 entry_cutoff=dtime(14, 30), escape=dtime(10, 0)),
    "RC60": dict(desc="CONTROL random-pick rotation, 14:00 window "
                      "(isolates the coil/pressure ranking)",
                 entry_cutoff=dtime(14, 0), rand=True),
    "R062": dict(desc="STACK under 10bps/side slippage stress",
                 entry_cutoff=dtime(14, 0), escape=dtime(10, 0),
                 slip=0.001),
    "R063": dict(desc="STACK coverage-robustness: candidates limited "
                      "to walk-8 depth",
                 entry_cutoff=dtime(14, 0), escape=dtime(10, 0),
                 cand_top=8),
    "R070": dict(desc="C38 candidate: C37 rotation + EMA 9>21 gate",
                 entry_cutoff=dtime(14, 30), escape=dtime(10, 0),
                 sim_extra={"ema_gate": (9, 21)}),
    # ---- B-series (2026-08-12): PROFIT BANKING UNDER ROTATION ----
    # User question after Paper Day 7 (BE peaked +6.2% / +$921 unrealized
    # and was flattened at +0.71%): "backtest banking at 6%".
    # Prior art rejected early exits FOUR times (S019-S027 breakeven,
    # S033-S036 time stops, R-Phase3 breakeven floors, F-series brackets)
    # -- but ALL of those were measured on STATIC configs where exiting
    # early means sitting in cash. Under rotation an early bank FREES THE
    # TICKET to re-pick, which is different economics and untested.
    # B000 is the rotation-path identity gate (must reproduce R061).
    "B000": dict(desc="IDENTITY: C37 baseline, no banking (= R061)",
                 entry_cutoff=dtime(14, 30), escape=dtime(10, 0)),
    "B006": dict(desc="C37 + FULL bank at +6% (the ask)",
                 entry_cutoff=dtime(14, 30), escape=dtime(10, 0),
                 sim_extra={"bank_all_at": 6.0}),
    "B004": dict(desc="adjacency: full bank at +4%",
                 entry_cutoff=dtime(14, 30), escape=dtime(10, 0),
                 sim_extra={"bank_all_at": 4.0}),
    "B005": dict(desc="adjacency: full bank at +5%",
                 entry_cutoff=dtime(14, 30), escape=dtime(10, 0),
                 sim_extra={"bank_all_at": 5.0}),
    "B008": dict(desc="adjacency: full bank at +8%",
                 entry_cutoff=dtime(14, 30), escape=dtime(10, 0),
                 sim_extra={"bank_all_at": 8.0}),
    "B010": dict(desc="adjacency: full bank at +10%",
                 entry_cutoff=dtime(14, 30), escape=dtime(10, 0),
                 sim_extra={"bank_all_at": 10.0}),
    "B015": dict(desc="adjacency: full bank at +15%",
                 entry_cutoff=dtime(14, 30), escape=dtime(10, 0),
                 sim_extra={"bank_all_at": 15.0}),
    "B025": dict(desc="adjacency far end: full bank at +25%",
                 entry_cutoff=dtime(14, 30), escape=dtime(10, 0),
                 sim_extra={"bank_all_at": 25.0}),
    # partial banking: keep the runner, bank 1/3 at +6%
    "B06P": dict(desc="C37 + PARTIAL bank 1/3 at +6% (pressure-skip on)",
                 entry_cutoff=dtime(14, 30), escape=dtime(10, 0),
                 sim_extra={"scale_out_at": 6.0}),
    "B06U": dict(desc="C37 + PARTIAL bank 1/3 at +6%, unconditional",
                 entry_cutoff=dtime(14, 30), escape=dtime(10, 0),
                 sim_extra={"scale_out_at": 6.0,
                            "scale_out_pressure_skip": None}),
    # ---- V-series (2026-08-12): THE LIVE SPREAD VETO, MODELLED ----
    # Live refuses any entry whose inside book is wider than 0.5%; the
    # sim never modelled this (it pays a 50bps premarket haircut and
    # takes the trade). On Paper Day 7 the veto blocked EVERY premarket
    # rank-1 pick, incl. SMWB which held rank 1 for ~15 cycles and then
    # ran +25%. So live has been running a strictly more restrictive
    # strategy than the one that earned $774,534 -- the benchmark does
    # not measure what we actually trade. This series prices it.
    # NOTE: no L2 history exists. The proxy is median 1-min bar range
    # over the 10 bars BEFORE entry, so thresholds are NOT comparable to
    # the live 0.5% inside-spread number. Read the sweep by VETO RATE,
    # not by the threshold.
    "V000": dict(desc="IDENTITY: C37, no veto (= B000 $774,534)",
                 entry_cutoff=dtime(14, 30), escape=dtime(10, 0)),
    "V050": dict(desc="veto entries with proxy > 0.5%",
                 entry_cutoff=dtime(14, 30), escape=dtime(10, 0),
                 spread_veto=0.5),
    "V100": dict(desc="veto entries with proxy > 1.0%",
                 entry_cutoff=dtime(14, 30), escape=dtime(10, 0),
                 spread_veto=1.0),
    "V200": dict(desc="veto entries with proxy > 2.0%",
                 entry_cutoff=dtime(14, 30), escape=dtime(10, 0),
                 spread_veto=2.0),
    "V300": dict(desc="veto entries with proxy > 3.0%",
                 entry_cutoff=dtime(14, 30), escape=dtime(10, 0),
                 spread_veto=3.0),
    "V500": dict(desc="veto entries with proxy > 5.0%",
                 entry_cutoff=dtime(14, 30), escape=dtime(10, 0),
                 spread_veto=5.0),
    "V800": dict(desc="veto entries with proxy > 8.0%",
                 entry_cutoff=dtime(14, 30), escape=dtime(10, 0),
                 spread_veto=8.0),
    # CONTROLS: identical machinery, proxy read from a RANDOM other bar
    # window in the same day -- same veto RATE, zero information. If the
    # real veto does no better than this, it is just 'trade less'.
    "VC10": dict(desc="CONTROL shuffled proxy, 1.0% cap",
                 entry_cutoff=dtime(14, 30), escape=dtime(10, 0),
                 spread_veto=1.0, veto_shuffle=True),
    "VC30": dict(desc="CONTROL shuffled proxy, 3.0% cap",
                 entry_cutoff=dtime(14, 30), escape=dtime(10, 0),
                 spread_veto=3.0, veto_shuffle=True),
    # ---- C38 FULL BATTERY (2026-08-13) on the V200 candidate ----
    # Finer adjacency across the cliff between 1.0% and 3.0%.
    "V150": dict(desc="adjacency: veto proxy > 1.5%",
                 entry_cutoff=dtime(14, 30), escape=dtime(10, 0),
                 spread_veto=1.5),
    "V250": dict(desc="adjacency: veto proxy > 2.5%",
                 entry_cutoff=dtime(14, 30), escape=dtime(10, 0),
                 spread_veto=2.5),
    "V175": dict(desc="adjacency: veto proxy > 1.75%",
                 entry_cutoff=dtime(14, 30), escape=dtime(10, 0),
                 spread_veto=1.75),
    # stress + robustness on the candidate
    "VS20": dict(desc="C38 cand under 10bps/side slippage stress",
                 entry_cutoff=dtime(14, 30), escape=dtime(10, 0),
                 spread_veto=2.0, slip=0.001),
    "VW20": dict(desc="C38 cand coverage robustness: walk-8 candidates",
                 entry_cutoff=dtime(14, 30), escape=dtime(10, 0),
                 spread_veto=2.0, cand_top=8),
    "VL20": dict(desc="C38 cand lookback robustness: 5-bar window",
                 entry_cutoff=dtime(14, 30), escape=dtime(10, 0),
                 spread_veto=2.0, veto_lookback=5),
    "VL21": dict(desc="C38 cand lookback robustness: 20-bar window",
                 entry_cutoff=dtime(14, 30), escape=dtime(10, 0),
                 spread_veto=2.0, veto_lookback=20),
    # controls
    "VC20": dict(desc="CONTROL shuffled proxy at the candidate cap 2.0%",
                 entry_cutoff=dtime(14, 30), escape=dtime(10, 0),
                 spread_veto=2.0, veto_shuffle=True),
    # LEAK DETECTOR -- deliberately NON-causal, never adoptable. The
    # causal candidate must score clearly BELOW this clairvoyant twin;
    # if they tie, the "causal" version is peeking.
    "VF20": dict(desc="LEAK DETECTOR: same veto from POST-entry bars",
                 entry_cutoff=dtime(14, 30), escape=dtime(10, 0),
                 spread_veto=2.0, veto_future=True),
    # CAUSAL-POOL pair: drops the hindsight day-high-gain pool cut.
    "VP00": dict(desc="LEAK AUDIT: C37 baseline on a causal pool",
                 entry_cutoff=dtime(14, 30), escape=dtime(10, 0),
                 causal_pool=True),
    "VP20": dict(desc="LEAK AUDIT: C38 candidate on a causal pool",
                 entry_cutoff=dtime(14, 30), escape=dtime(10, 0),
                 spread_veto=2.0),
    # ---- N-series (2026-08-13): the champion re-measured HONESTLY ----
    # Causal pool is now the default. C37 and the two configs that
    # justified adopting rotation are re-run here; the old numbers were
    # all inflated by the hindsight pool cut.
    "C37H": dict(desc="C37 HONEST: rotation, 14:30 window, 10:00 escape",
                 entry_cutoff=dtime(14, 30), escape=dtime(10, 0)),
    "N023": dict(desc="HONEST no-rotation baseline (same-name ladder)",
                 entry_cutoff=dtime(14, 30), escape=dtime(10, 0),
                 rotate=False),
    "NC60": dict(desc="HONEST CONTROL: random-pick rotation",
                 entry_cutoff=dtime(14, 30), escape=dtime(10, 0),
                 rand=True),
    "N060": dict(desc="HONEST adjacency: 14:00 window",
                 entry_cutoff=dtime(14, 0), escape=dtime(10, 0)),
    "N062": dict(desc="HONEST stress: 10bps/side slippage",
                 entry_cutoff=dtime(14, 30), escape=dtime(10, 0),
                 slip=0.001),
    "VOLD": dict(desc="LEGACY biased pool, reproduces the old $774,534",
                 entry_cutoff=dtime(14, 30), escape=dtime(10, 0),
                 biased_pool=True),
    # ---- T-series (2026-08-13): STALL RELEASE UNDER ROTATION ----
    # Hold-time study (797 legs): winners median 15m, LOSERS median 8m,
    # 78% of all profit lands in the 10-30m band, sub-10m trades LOSE in
    # aggregate, and only 8/797 legs ran past 180m -- yet all three paper
    # sessions held 5-6h. A 9-minute exit would cut into the losing
    # bucket (and time stops already lost 5x); this instead frees a DEAD
    # ticket so rotation can redeploy it. Untested under rotation: the
    # static tests parked the freed capital in cash.
    "T010": dict(desc="stall release: cut flat/red after 10m",
                 entry_cutoff=dtime(14, 30), escape=dtime(10, 0),
                 sim_extra={"time_stop_min": 10}),
    "T015": dict(desc="stall release 15m",
                 entry_cutoff=dtime(14, 30), escape=dtime(10, 0),
                 sim_extra={"time_stop_min": 15}),
    "T020": dict(desc="stall release 20m",
                 entry_cutoff=dtime(14, 30), escape=dtime(10, 0),
                 sim_extra={"time_stop_min": 20}),
    "T030": dict(desc="stall release 30m",
                 entry_cutoff=dtime(14, 30), escape=dtime(10, 0),
                 sim_extra={"time_stop_min": 30}),
    "T045": dict(desc="stall release 45m",
                 entry_cutoff=dtime(14, 30), escape=dtime(10, 0),
                 sim_extra={"time_stop_min": 45}),
    "T060": dict(desc="stall release 60m",
                 entry_cutoff=dtime(14, 30), escape=dtime(10, 0),
                 sim_extra={"time_stop_min": 60}),
    # trend/volume conditioned: spare the ticket while BUYERS hold it
    "TP20": dict(desc="20m stall release, spared while pressure >= 0",
                 entry_cutoff=dtime(14, 30), escape=dtime(10, 0),
                 sim_extra={"time_stop_min": 20, "time_stop_pressure": 0.0}),
    "TP21": dict(desc="20m stall release, spared while pressure >= +0.3",
                 entry_cutoff=dtime(14, 30), escape=dtime(10, 0),
                 sim_extra={"time_stop_min": 20, "time_stop_pressure": 0.3}),
    "TP30": dict(desc="30m stall release, spared while pressure >= 0",
                 entry_cutoff=dtime(14, 30), escape=dtime(10, 0),
                 sim_extra={"time_stop_min": 30, "time_stop_pressure": 0.0}),
    # "not working" bar raised above breakeven
    "TG20": dict(desc="20m: cut unless up >= +2%",
                 entry_cutoff=dtime(14, 30), escape=dtime(10, 0),
                 sim_extra={"time_stop_min": 20, "time_stop_progress": 2.0}),
    "TG21": dict(desc="20m: cut unless up >= +5%",
                 entry_cutoff=dtime(14, 30), escape=dtime(10, 0),
                 sim_extra={"time_stop_min": 20, "time_stop_progress": 5.0}),
    # CONTROL: inverted pressure condition -- spares the DEAD ones and
    # cuts the live ones. Must lose badly.
    "TC20": dict(desc="CONTROL 20m, pressure condition INVERTED",
                 entry_cutoff=dtime(14, 30), escape=dtime(10, 0),
                 sim_extra={"time_stop_min": 20, "time_stop_pressure": 0.0,
                            "time_stop_pressure_inv": True}),
}


def bars_for(sym, date):
    f = M1 / f"{sym}_{date}.csv"
    if not f.exists() or f.read_text(errors="ignore").startswith("EMPTY"):
        return None
    try:
        df = pd.read_csv(f, index_col=0, parse_dates=True)
        df.index = df.index.tz_convert("America/New_York")
        return df
    except Exception:
        return None


def day_candidates(cs, date, dfs, top=16, causal_pool=True):
    """Pre-compute per-candidate causal series needed by the ranker.

    LEAK NOTE (audited 2026-08-13): `gain_pct` in the gappers files is
    the DAY-HIGH gain -- a full-day statistic. Sorting by it and cutting
    to `top` therefore selects the POOL with hindsight, even though
    rank_at orders that pool causally. Measured impact: bars exist for
    only ~17 names/day (median) and the top-16 cut keeps 16 of them, so
    the explicit sort removes a median of 1 name/day. The dominant bias
    is UPSTREAM and disclosed: minute bars were only ever fetched to
    full-day-gain depth, so the universe itself is coverage-biased.
    causal_pool=True drops the hindsight sort and takes every candidate
    that has bars -- it cannot repair the upstream coverage bias, but it
    removes the one leak this file controls."""
    # DEFAULT CHANGED 2026-08-13: causal pool is now the default. Every
    # rotation number produced BEFORE this date (R0xx, B0xx, V0xx incl.
    # the adopted "C37 = $774,534") was measured on the hindsight-cut
    # pool and is NOT comparable to anything produced after it. Configs
    # that need the old behaviour must set biased_pool=True explicitly.
    if causal_pool:
        pool = [c for c in cs
                if (M1 / f"{c['symbol']}_{date}.csv").exists()]
    else:
        pool = sorted(cs, key=lambda x: -x["gain_pct"])[:top]
    out = []
    for c in pool:
        pc = c.get("prev_close") or 0
        if pc <= 0:
            continue
        df = dfs.get(c["symbol"])
        if df is None:
            df = bars_for(c["symbol"], date)
            dfs[c["symbol"]] = df
        if df is None:
            continue
        thr = 1.10 * pc
        cross = None
        for ts, hi in zip(df.index, df["High"].values):
            if ts.time() > dtime(14, 0):
                break
            if float(hi) >= thr:
                cross = ts.time()
                break
        if cross is None:
            continue
        w7 = df[df.index.time <= dtime(7, 0)]
        gap7 = (float(w7["Close"].iloc[-1]) / pc - 1) * 100 if len(w7) \
            else None
        pm = px.premkt_metrics(df, pc)
        pmh = pc * (1 + pm["pm_high_gain"] / 100) if pm else None
        out.append({"c": c, "df": df, "pc": pc, "cross": cross,
                    "gap7": gap7, "halal": None, "pmh": pmh})
    return out


def rank_at(cands, t, top=None, fc=None):
    """Causal rank at clock time t: crossed names only; coiled group
    first (last<=t close / high<=t >= 0.95), pressure(30) order within.

    `fc` is an optional feature-cache dict for this date (see
    plan/feature_cache.py). It is a pure accelerator: values are the
    same numbers this function would compute, verified row-by-row by
    `feature_cache.py --verify`. Any cache miss falls through to live
    computation, so a partial cache is safe, never silently wrong."""
    scored = []
    key = f"{t.hour:02d}{t.minute:02d}"
    for r in cands:
        if r["cross"] > t:
            continue
        hit = fc.get(r["c"]["symbol"], {}).get(key) if fc else None
        if hit is not None:
            _last, _hi, coil, prs = hit
        else:
            w = r["df"][r["df"].index.time <= t]
            if len(w) < 3:
                continue
            last = float(w["Close"].iloc[-1])
            hi = float(w["High"].max())
            coil = last / hi if hi > 0 else 0
            prs = None
            if len(w) >= 5:
                cd = dt.Candles(w)
                prs = cd.pressure(cd.n - 1, 30, 20_000)
        scored.append(((0 if coil >= 0.95 else 1,
                        -(prs if prs is not None else -1)), r))
    scored.sort(key=lambda x: x[0])
    rs = [r for _, r in scored]
    return rs[:top] if top else rs


def gates_ok(r, is_top):
    lim = 35.0 if is_top else 20.0
    if r["gap7"] is None or r["gap7"] > lim:
        return False
    if r["halal"] is None:
        r["halal"] = axb.halal_pt(r["c"]["symbol"], r["c"]["date"],
                                  r["pc"])
    return r["halal"]


def spread_proxy(df, ts, lookback=10):
    """Proxy for BOOK WIDTH at the moment just before `ts`.

    We have no historical L2, so the live 0.5% inside-spread veto cannot
    be replayed exactly. The honest stand-in is the median 1-minute bar
    range (H-L)/C over the `lookback` bars ENDING BEFORE ts -- a wide,
    gappy, low-print tape is exactly what a wide book produces, and
    using bars strictly before entry keeps our own trigger bar out of
    the estimate. Returns percent, or None when there is not enough
    tape (treated as NOT vetoed, matching live where a missing book
    reading falls through to the other gates).
    LOUD LIMITATION: this bounds the veto's effect, it does not measure
    the real spread. Bar range conflates volatility with book width.
    """
    w = df[df.index < ts]
    if len(w) < lookback:
        return None
    tail = w.iloc[-lookback:]
    # LEAK GATE: the estimate may never touch the entry bar or anything
    # after it. Asserted every call -- a silent off-by-one here would
    # manufacture a future signal that looks like edge.
    assert tail.index.max() < ts, (
        f"FUTURE LEAK in spread_proxy: window max {tail.index.max()} "
        f">= entry {ts}")
    c = tail["Close"].values
    rng = (tail["High"].values - tail["Low"].values)
    vals = [(r / p) * 100 for r, p in zip(rng, c) if p > 0]
    if not vals:
        return None
    vals.sort()
    n = len(vals)
    return vals[n // 2] if n % 2 else (vals[n // 2 - 1] + vals[n // 2]) / 2


def future_proxy(df, ts, lookback=10):
    """LEAK DETECTOR (deliberately non-causal -- never a candidate).

    Same statistic computed from the `lookback` bars AT AND AFTER the
    entry, i.e. it knows how the tape behaved after we committed. If the
    causal version scores about the same as this, the 'causal' version
    is peeking; a genuinely causal signal should be clearly WEAKER than
    its clairvoyant twin. Reported alongside, never adopted."""
    w = df[df.index >= ts]
    if len(w) < lookback:
        return None
    tail = w.iloc[:lookback]
    c = tail["Close"].values
    rng = (tail["High"].values - tail["Low"].values)
    vals = sorted((r / p) * 100 for r, p in zip(rng, c) if p > 0)
    if not vals:
        return None
    n = len(vals)
    return vals[n // 2] if n % 2 else (vals[n // 2 - 1] + vals[n // 2]) / 2


def _shuffled_proxy(df, ts, lookback, date, sym, k):
    """CONTROL: same machinery, but the proxy is read from a RANDOM
    other bar-window in the same day. Preserves the marginal
    distribution (so the veto RATE matches) while destroying the
    information. If the real veto performs no better than this, the
    proxy carries nothing and the veto is just 'trade less'."""
    import random as _rnd
    w = df[df.index.time < dtime(15, 0)]
    if len(w) < lookback + 2:
        return None
    rng = _rnd.Random(f"vc-{date}-{sym}-{k}")
    j = rng.randrange(lookback, len(w))
    return spread_proxy(df, w.index[j], lookback)


def run_day(cands, date, cfg, stats=None, fc=None):
    entry_open = cfg.get("entry_open", dtime(7, 0))
    cutoff = cfg.get("entry_cutoff", dtime(12, 0))
    rotate = cfg.get("rotate", True)
    trades = []
    t = entry_open
    ticket_i = 0
    last_sym, last_pnl = None, 0.0
    while ticket_i < len(TICKETS):
        if t >= cutoff:
            break
        # pick at time t
        pool = rank_at(cands, t, cfg.get("top"), fc)
        if cfg.get("rand"):
            import random as _rnd
            _rnd.Random(f"rc60-{date}-{ticket_i}").shuffle(pool)
        pick = None
        if not rotate and last_sym is not None:
            pick = next((r for r in pool
                         if r["c"]["symbol"] == last_sym), None)
        elif cfg.get("on_win") == "stay" and last_sym is not None \
                and last_pnl > 0:
            pick = next((r for r in pool
                         if r["c"]["symbol"] == last_sym), None)
        if pick is None:
            for i, r in enumerate(pool):
                if gates_ok(r, i == 0):
                    pick = r
                    break
        if pick is None:
            t = _step(t)
            continue
        # simulate ONE ticket on this name from t
        df = pick["df"]
        w = df[(df.index.time >= entry_open) & (df.index.time < EXIT_END)]
        if len(w) < 20:
            t = _step(t)
            continue
        esc = cfg.get("escape")
        kw = dict(SIMKW)
        kw.update(cfg.get("sim_extra") or {})
        if cfg.get("slip"):
            kw["slippage_bps"] = cfg["slip"] * 1e4   # engine kwarg name
        if pick.get("pmh"):
            kw["extra_break_high"] = pick["pmh"]   # champion parity:
            # the premarket-high stop-buy travels OUTSIDE the sim dict
        tr = dt.simulate_trades(
            w, prev_close=pick["pc"], budget=TICKETS[ticket_i],
            entry_start=max(t, pick["cross"]), **kw)
        tr = [x for x in tr if x.get("entry_time") is not None]
        if not tr:
            # never triggered: stale-pick escape re-ranks at esc, else
            # step forward and re-pick
            t = esc if (esc and t < esc) else _step(t)
            last_sym = pick["c"]["symbol"] if not rotate else last_sym
            continue
        first_entry = tr[0]["entry_time"]
        # ---- LIVE-PARITY SPREAD VETO (V-series) ----
        # Live refuses any entry whose inside book is wider than the cap;
        # the sim has never modelled this -- it only pays a 50bps
        # premarket haircut and takes the trade. Applied here, post-hoc
        # at the entry bar, so NO engine change is needed (identity of
        # every prior result is untouched by construction).
        vcap = cfg.get("spread_veto")
        if vcap:
            lb = cfg.get("veto_lookback", 10)
            if cfg.get("veto_shuffle"):
                prox = _shuffled_proxy(df, first_entry, lb, date,
                                       pick["c"]["symbol"], ticket_i)
            elif cfg.get("veto_future"):
                prox = future_proxy(df, first_entry, lb)   # LEAK DETECTOR
            else:
                prox = spread_proxy(df, first_entry, lb)
            if stats is not None:
                stats["checked"] = stats.get("checked", 0) + 1
            if prox is not None and prox > vcap:
                if stats is not None:
                    stats["vetoed"] = stats.get("vetoed", 0) + 1
                # vetoed: no ticket consumed, step past the trigger bar
                # and re-rank -- exactly what live does when the book is
                # too wide (SMWB was vetoed 15 cycles running on Day 7).
                t = _step(first_entry.time())
                continue
        grp = [x for x in tr if x["entry_time"] == first_entry]
        pnl = sum(x["pnl"] for x in grp)
        exit_t = max(x["exit_time"] for x in grp).time()
        for x in grp:
            x["ticket"] = ticket_i
            x["symbol"] = pick["c"]["symbol"]
        trades += grp
        ticket_i += 1
        last_sym, last_pnl = pick["c"]["symbol"], pnl
        t = _step(max(t, exit_t))
    return trades


def _step(t):
    m = t.hour * 60 + t.minute + SCAN_STEP
    m = (m // SCAN_STEP) * SCAN_STEP
    return dtime(min(m // 60, 23), m % 60)


def out_dd(daily):
    eq = pk = dd = 0.0
    for _, pnl, _ in daily:
        eq += pnl
        pk = max(pk, eq)
        dd = max(dd, pk - eq)
    return dd


def run(cfg_id, max_days=None):
    cfg = CFGS[cfg_id]
    print(f"{cfg_id}: {cfg['desc']}", flush=True)
    out = {}
    for lab in ("year", "y2025"):
        byday = px.load_by_day(lab, 50, "novol")
        stats = {}
        total, days, monthly = 0.0, 0, defaultdict(float)
        daily = []          # per-traded-day P&L, for drawdown/exposure
        items = sorted(byday.items())
        if max_days:
            items = items[:max_days]
        for n, (date, cs) in enumerate(items, 1):
            dfs = {}
            cands = day_candidates(cs, date, dfs,
                                   cfg.get("cand_top", 16),
                                   not cfg.get("biased_pool", False))
            if not cands:
                continue
            fc = _featcache_for(date) if USE_FEATCACHE else None
            tr = run_day(cands, date, cfg, stats, fc)
            if tr:
                p = sum(x["pnl"] for x in tr)
                total += p
                days += 1
                monthly[date[:7]] += p
                daily.append((date, p, len({x.get("ticket")
                                            for x in tr})))
            if n % 50 == 0:
                print(f"  ..{lab} {n}/{len(items)} "
                      f"({days}d ${total:+,.0f})", flush=True)
        negm = sum(1 for v in monthly.values() if v < 0)
        print(f" {cfg_id} {lab:<6} {days:>4}d ${total:>+12,.0f} "
              f"{negm}/{len(monthly)}  maxDD ${out_dd(daily):>9,.0f}  "
              f"[{cfg['desc']}]", flush=True)
        vch, vvt = stats.get("checked", 0), stats.get("vetoed", 0)
        if vch:
            print(f"   veto: {vvt}/{vch} entries blocked "
                  f"({100*vvt/vch:.1f}%)", flush=True)
        # RISK COLUMNS (2026-08-13). Total P&L and negative months alone
        # cannot distinguish edge from leverage -- the S-campaign learned
        # that when pressure-scaled sizing "won" purely by deploying more
        # capital. Drawdown and ticket usage make that visible.
        eq = pk = dd = 0.0
        for _, pnl, _ in daily:
            eq += pnl
            pk = max(pk, eq)
            dd = max(dd, pk - eq)
        wins = sum(1 for _, pnl, _ in daily if pnl > 0)
        tks = [t for _, _, t in daily]
        out[lab] = {"total": round(total), "days": days, "negm": negm,
                    "nmonths": len(monthly),
                    "veto_checked": vch, "veto_blocked": vvt,
                    "max_dd": round(dd),
                    "max_dd_pct_of_peak": (round(100 * dd / pk, 1)
                                           if pk > 0 else None),
                    "win_days_pct": (round(100 * wins / len(daily), 1)
                                     if daily else None),
                    "worst_day": round(min((p for _, p, _ in daily),
                                           default=0)),
                    "best_day": round(max((p for _, p, _ in daily),
                                          default=0)),
                    "tickets_per_day_avg": (round(sum(tks) / len(tks), 2)
                                            if tks else None),
                    "monthly": {k: round(v) for k, v in
                                sorted(monthly.items())}}
    res = json.loads(RES_F.read_text()) if RES_F.exists() else {}
    res[cfg_id] = {"desc": cfg["desc"], **out}
    RES_F.write_text(json.dumps(res, indent=1))
    return out


if __name__ == "__main__":
    md = None
    argv = sys.argv[1:]
    if "--days" in argv:
        i = argv.index("--days")
        md = int(argv[i + 1])
        argv = argv[:i] + argv[i + 2:]
    args = [a for a in argv if not a.startswith("--")]
    for cid in (args or ["R020"]):
        run(cid, md)
