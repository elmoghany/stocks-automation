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


_RANK_MODE = [None]      # set per-config by run_day; None = champion key
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

# ---- EXIT-KWARG WHITELIST (2026-09-01, harness correction) ----
# AUDIT FINDING (read-only audit 2026-09-01, cited in NOTES): every
# XH/XP/K/KR config set trail_pct=999, stop_pct=99 to "remove all
# exits", but SIMKW inherits Z104's pressure_trail=(10, 0.3, 0.3, 10,
# 40), which sim_extra never overrode; day-trading.py re-arms a 10%
# trail from peak when 10-bar pressure <= -0.3 (40% when >= +0.3).
# So "hold-to-flatten" configs were in fact pressure-trailed; K6S's
# 'stop' exits were +$24,275 over 219 exits vs window-close -$5,535
# over 264. The 2026-08-27 "every exit subtracts" conclusion was
# measured on mislabeled configs (RETRACTION in NOTES 2026-09-01).
# FIX: every exit-related kwarg is listed here; a config that names an
# `exit_mode` gets the FULL set resolved explicitly (asserted), so no
# exit machinery can ever be inherited silently again. `dyn_trail` /
# `dyn_stop` are locals of simulate_trades (derived from atr_trail /
# atr_stop), not kwargs, hence covered via those two.
EXIT_KWARGS = (
    "trail_pct", "stop_pct", "pressure_trail", "atr_trail", "atr_stop",
    "breakeven_at", "struct_stop_bars", "time_stop_min",
    "time_stop_progress", "time_stop_pressure", "time_stop_pressure_inv",
    "scale_out_at", "scale_out_2", "scale_out_frac",
    "scale_out_pressure_skip", "scale_out_frac_pressure", "bank_all_at",
    "pressure_exit", "sell_mode", "target_pct", "target_r", "wick_guard",
    "trail_widen_at", "tighten_at_r", "monster_mode",
)
# EXIT_HOLD: flatten only. Every exit kwarg None except the three the
# engine needs to stay in its trail branch without ever firing: stop
# 99% below entry, trail 99.9% below peak, no pattern exits. The ONLY
# exit that can print is "window-close flatten".
EXIT_HOLD = {k: None for k in EXIT_KWARGS}
EXIT_HOLD.update(sell_mode="target_stop_only", trail_pct=999, stop_pct=99)
# EXIT_PTRAIL: HOLD + the pressure-modulated trail that the mislabeled
# K/XH configs were actually running (10% from peak on selling
# pressure, 40% on buying pressure). This is what "K6S as run" was.
EXIT_PTRAIL = dict(EXIT_HOLD, pressure_trail=(10, 0.3, 0.3, 10, 40))
EXIT_MODES = {"HOLD": EXIT_HOLD, "PTRAIL": EXIT_PTRAIL}


def build_simkw(cfg_id, cfg, echo=True):
    """Resolve a config's effective simulate_trades kwargs.

    Order: SIMKW (Z104 machinery) -> exit_mode block (if any) ->
    sim_extra (explicit per-config overrides). For any config carrying
    `exit_mode`, ASSERT the whole EXIT_KWARGS set is explicitly present
    and equals the mode's values unless sim_extra overrode it. Prints
    the resolved exit kwargs at run start so the label and the
    machinery can be checked against each other by eye."""
    kw = dict(SIMKW)
    em = cfg.get("exit_mode")
    extra = cfg.get("sim_extra") or {}
    if em:
        if em not in EXIT_MODES:
            raise ValueError(f"{cfg_id}: unknown exit_mode {em!r}")
        kw.update(EXIT_MODES[em])
    kw.update(extra)
    if em:
        missing = [k for k in EXIT_KWARGS if k not in kw]
        assert not missing, f"{cfg_id}: exit kwargs unresolved: {missing}"
        for k in EXIT_KWARGS:
            want = extra[k] if k in extra else EXIT_MODES[em][k]
            assert kw[k] == want, (
                f"{cfg_id}: exit kwarg {k} = {kw[k]!r}, expected {want!r}")
    if echo:
        shown = {k: kw.get(k) for k in EXIT_KWARGS if kw.get(k) is not None}
        print(f"  exit kwargs [{cfg_id}] mode={em or 'inherited'}: "
              f"{shown}", flush=True)
        if em == "HOLD":
            assert shown == {"trail_pct": 999, "stop_pct": 99,
                             "sell_mode": "target_stop_only"}, shown
    return kw


def exit_category(reason):
    """Bucket an engine exit reason string for the per-label report."""
    r = (reason or "").lower()
    if r.startswith("window-close"):
        return "window-close"
    if r.startswith("stop"):
        return "stop"
    if r.startswith("target"):
        return "target/bank"
    if r.startswith("scale-out"):
        return "scale-out"
    if r.startswith("bearish"):
        return "bearish"
    if r.startswith("pressure-flip"):
        return "pressure-flip"
    if r.startswith("time-stop"):
        return "time-stop"
    return "other"

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
    # ---- GATE RE-BASELINE (2026-08-14) ----
    # Identical parameters to C37H; the difference is the ENVIRONMENT:
    # run with HALAL_STRICT=1 so halal_pt uses the live gate semantics
    # (unknown industry refuses, word-boundary matching, no
    # liabilities-for-debt approximation). Separate config id so this
    # row can never overwrite the champion's C37H entry.
    "C37S": dict(desc="C37 re-baselined under the LIVE halal gate "
                      "(HALAL_STRICT=1)",
                 entry_cutoff=dtime(14, 30), escape=dtime(10, 0)),
    # C37E (2026-08-14): identical parameters to C37S; the difference
    # is again the ENVIRONMENT: HALAL_STRICT=1 PT_FILED=1 with the
    # EDGAR-backfilled pt_halal cache, so the strict gate can verify
    # names on their REAL filed quarterlies (true filing dates) instead
    # of refusing everything outside the old 133-symbol yf cache.
    # Tightened LOWER bound: should land between C37S ($405,826) and
    # C37H ($665,667).
    "C37E": dict(desc="C37 under live gate + EDGAR filed-date cache",
                 entry_cutoff=dtime(14, 30), escape=dtime(10, 0)),
    # C37F (2026-08-21, W-campaign Phase 0.1): identical parameters AND
    # environment to C37E (HALAL_STRICT=1 PT_FILED=1); the difference is
    # the DATA: the full-breadth m1 backfill (plan/backfill_m1_full.py)
    # closed the bar-coverage-by-full-day-gain bias, so the causal pool
    # is now every candidate/day (~213) instead of the ~17 that had
    # gain-selected bars. Separate id so C37E's pre-backfill row is
    # never overwritten. Run: HALAL_STRICT=1 PT_FILED=1 ROTSHARD=full.
    # FINAL DECISIVE TEST (2026-08-27): every control so far compared
    # RANKED-with-costs against RANDOM-without-costs, which flatters
    # the ranking. Run both under IDENTICAL 10bps slippage. If ranked
    # still wins, the edge is real but small; if not, the whole result
    # is drift harvesting and selection contributes nothing.
    "K6S": dict(desc="K6 under 10bps/side slippage",
                entry_cutoff=dtime(14, 30), escape=dtime(10, 0), topk=6,
                slip=0.001,
                sim_extra={"trail_pct": 999, "stop_pct": 99,
                           "scale_out_at": None, "pressure_exit": None,
                           "sell_mode": "target_stop_only"}),
    "KR6S": dict(desc="CONTROL: RANDOM 6 under the SAME 10bps slippage",
                 entry_cutoff=dtime(14, 30), escape=dtime(10, 0), topk=6,
                 rand=True, slip=0.001,
                 sim_extra={"trail_pct": 999, "stop_pct": 99,
                            "scale_out_at": None, "pressure_exit": None,
                            "sell_mode": "target_stop_only"}),
    "K6": dict(desc="XHB + 6 concurrent names",
               entry_cutoff=dtime(14, 30), escape=dtime(10, 0), topk=6,
               sim_extra={"trail_pct": 999, "stop_pct": 99,
                          "scale_out_at": None, "pressure_exit": None,
                          "sell_mode": "target_stop_only"}),
    "K7": dict(desc="XHB + 7 concurrent (full ticket schedule, $100k cap)",
               entry_cutoff=dtime(14, 30), escape=dtime(10, 0), topk=7,
               sim_extra={"trail_pct": 999, "stop_pct": 99,
                          "scale_out_at": None, "pressure_exit": None,
                          "sell_mode": "target_stop_only"}),
    "KR7": dict(desc="CONTROL: RANDOM 7 concurrent (isolates ranking)",
                entry_cutoff=dtime(14, 30), escape=dtime(10, 0), topk=7,
                rand=True,
                sim_extra={"trail_pct": 999, "stop_pct": 99,
                           "scale_out_at": None, "pressure_exit": None,
                           "sell_mode": "target_stop_only"}),
    "K7S": dict(desc="K7 under 10bps/side slippage stress",
                entry_cutoff=dtime(14, 30), escape=dtime(10, 0), topk=7,
                slip=0.001,
                sim_extra={"trail_pct": 999, "stop_pct": 99,
                           "scale_out_at": None, "pressure_exit": None,
                           "sell_mode": "target_stop_only"}),
    # ---- XP-series (2026-08-27): the LAST untested exit combination.
    # XH disabled bearish-pattern exits ALONGSIDE the stop and trail
    # (sell_mode="target_stop_only"). But in the pre-backfill analysis
    # bearish-pattern exits were the single largest profit contributor
    # (+$1.6M over 1,450 exits) -- and they have NEVER been tested
    # WITHOUT the stop/trail attached. Hold-to-flatten + pattern exits
    # only is a genuinely different configuration.
    # XPR is its random control: if random+patterns matches, the
    # ranking still adds nothing and the campaign's answer is settled.
    "XP0": dict(desc="hold-to-flatten + BEARISH PATTERN exits only",
                entry_cutoff=dtime(14, 30), escape=dtime(10, 0),
                sim_extra={"trail_pct": 999, "stop_pct": 99,
                           "scale_out_at": None, "pressure_exit": None}),
    "XP1": dict(desc="hold + patterns + pressure-flip exits",
                entry_cutoff=dtime(14, 30), escape=dtime(10, 0),
                sim_extra={"trail_pct": 999, "stop_pct": 99,
                           "scale_out_at": None,
                           "pressure_exit": (10, 0.3, "profit")}),
    "XPR": dict(desc="CONTROL: RANDOM pick + hold + pattern exits",
                entry_cutoff=dtime(14, 30), escape=dtime(10, 0),
                rand=True,
                sim_extra={"trail_pct": 999, "stop_pct": 99,
                           "scale_out_at": None, "pressure_exit": None}),
    # ---- K-series (2026-08-27): CONCURRENCY on top of XHB. With
    # hold-to-flatten one ticket occupies the whole day, so 6 of 7 sit
    # idle -- the only remaining mechanism that MULTIPLIES a per-day
    # edge rather than shaving losses. k names are entered at the SAME
    # decision points the rotation loop already uses, each with
    # budget/k, each running the identical hold-to-flatten exits.
    # NOTE user constraint: live stays ONE position at a time; this is
    # a backtest-only measurement (user approval 2026-08-20).
    "K2": dict(desc="XHB + 2 concurrent names (budget split 2)",
               entry_cutoff=dtime(14, 30), escape=dtime(10, 0), topk=2,
               sim_extra={"trail_pct": 999, "stop_pct": 99,
                          "scale_out_at": None, "pressure_exit": None,
                          "sell_mode": "target_stop_only"}),
    "K3": dict(desc="XHB + 3 concurrent names (budget split 3)",
               entry_cutoff=dtime(14, 30), escape=dtime(10, 0), topk=3,
               sim_extra={"trail_pct": 999, "stop_pct": 99,
                          "scale_out_at": None, "pressure_exit": None,
                          "sell_mode": "target_stop_only"}),
    "K4": dict(desc="XHB + 4 concurrent names (budget split 4)",
               entry_cutoff=dtime(14, 30), escape=dtime(10, 0), topk=4,
               sim_extra={"trail_pct": 999, "stop_pct": 99,
                          "scale_out_at": None, "pressure_exit": None,
                          "sell_mode": "target_stop_only"}),
    "KR3": dict(desc="CONTROL: RANDOM 3 concurrent (isolates ranking)",
                entry_cutoff=dtime(14, 30), escape=dtime(10, 0), topk=3,
                rand=True,
                sim_extra={"trail_pct": 999, "stop_pct": 99,
                           "scale_out_at": None, "pressure_exit": None,
                           "sell_mode": "target_stop_only"}),
    # ---- XH controls (2026-08-27): XHB (+83,759, both years, maxDD
    # LOWER than baseline) must survive these before it means anything.
    # XHR is the decider: "buy a +10% gapper and hold to 15:00" may be
    # harvesting an intraday drift common to ALL gappers -- beta, not
    # edge. If random picks earn too, the ranking contributes nothing.
    "XHR": dict(desc="CONTROL: RANDOM pick + hold-to-flatten (beta test)",
                entry_cutoff=dtime(14, 30), escape=dtime(10, 0), rand=True,
                sim_extra={"trail_pct": 999, "stop_pct": 99,
                           "scale_out_at": None, "pressure_exit": None,
                           "sell_mode": "target_stop_only"}),
    "XHS": dict(desc="XHB under 10bps/side slippage stress",
                entry_cutoff=dtime(14, 30), escape=dtime(10, 0),
                slip=0.001,
                sim_extra={"trail_pct": 999, "stop_pct": 99,
                           "scale_out_at": None, "pressure_exit": None,
                           "sell_mode": "target_stop_only"}),
    "XHW": dict(desc="XHB coverage robustness: walk-8 candidate depth",
                entry_cutoff=dtime(14, 30), escape=dtime(10, 0),
                cand_top=8,
                sim_extra={"trail_pct": 999, "stop_pct": 99,
                           "scale_out_at": None, "pressure_exit": None,
                           "sell_mode": "target_stop_only"}),
    # ---- XH-series (2026-08-27): ARE THE EXITS EATING THE SIGNAL?
    # The IC study measured the tradeable corner at +2.52% mean/trade
    # with entry-at-next-print and HOLD TO FLATTEN -- no stop, no trail.
    # The harness applies C37's exits (-8% stop, 20% peak trail,
    # scale-out) and the same entries LOSE. Those exits were tuned on
    # the biased cache, whose survivors were +100-300% monsters; a 20%
    # trail is generous there and brutal on a name up 12%. Isolate the
    # exit machinery on the honest pool, one component at a time.
    # HOLD = trail/stop set out of reach + no scale-out + no pattern or
    # pressure exits => only the 15:00 window-close flatten can fire.
    "XHB": dict(desc="baseline rank + HOLD-to-flatten (exits isolated)",
                entry_cutoff=dtime(14, 30), escape=dtime(10, 0),
                sim_extra={"trail_pct": 999, "stop_pct": 99,
                           "scale_out_at": None, "pressure_exit": None,
                           "sell_mode": "target_stop_only"}),
    "XH0": dict(desc="gain_asc + HOLD-to-flatten (the IC study's own rule)",
                entry_cutoff=dtime(14, 30), escape=dtime(10, 0),
                rank_mode="gain_asc",
                sim_extra={"trail_pct": 999, "stop_pct": 99,
                           "scale_out_at": None, "pressure_exit": None,
                           "sell_mode": "target_stop_only"}),
    "XH1": dict(desc="gain_asc + STOP only (-8%, no trail)",
                entry_cutoff=dtime(14, 30), escape=dtime(10, 0),
                rank_mode="gain_asc",
                sim_extra={"trail_pct": 999, "stop_pct": 8,
                           "scale_out_at": None, "pressure_exit": None,
                           "sell_mode": "target_stop_only"}),
    "XH2": dict(desc="gain_asc + TRAIL only (20%, stop out of reach)",
                entry_cutoff=dtime(14, 30), escape=dtime(10, 0),
                rank_mode="gain_asc",
                sim_extra={"trail_pct": 20, "stop_pct": 99,
                           "scale_out_at": None, "pressure_exit": None,
                           "sell_mode": "target_stop_only"}),
    "XH3": dict(desc="gain_asc + wide stop 15%% + trail 20%%",
                entry_cutoff=dtime(14, 30), escape=dtime(10, 0),
                rank_mode="gain_asc",
                sim_extra={"trail_pct": 20, "stop_pct": 15,
                           "scale_out_at": None, "pressure_exit": None,
                           "sell_mode": "target_stop_only"}),
    # ---- IR-series (2026-08-27): RE-RANK, not re-filter. From the IC
    # study (IC-STUDY-honest-pool.md): c37_rank_score IC -0.0433 (ranks
    # backwards); gain_now IC -0.241..-0.032, 29/30 sign-stable, beats
    # both negative controls. Pre-registered pass bar: both years
    # independently positive, gain_desc control must LOSE, adjacency
    # coherent across the variants, negm better than C37F's 18/23.
    "IR000": dict(desc="IDENTITY: C37F (rank_mode off)",
                  entry_cutoff=dtime(14, 30), escape=dtime(10, 0)),
    "IRGA": dict(desc="RE-RANK: least-extended crosser first (gain_now asc)",
                 entry_cutoff=dtime(14, 30), escape=dtime(10, 0),
                 rank_mode="gain_asc"),
    "IRGC": dict(desc="RE-RANK: coil group, gain_now asc within",
                 entry_cutoff=dtime(14, 30), escape=dtime(10, 0),
                 rank_mode="gain_asc_coil"),
    "IRGD": dict(desc="CONTROL INVERTED: most-extended first (must lose)",
                 entry_cutoff=dtime(14, 30), escape=dtime(10, 0),
                 rank_mode="gain_desc"),
    "IRGN": dict(desc="gain_asc + no premarket entries (09:30 open)",
                 entry_open=dtime(9, 30), entry_cutoff=dtime(14, 30),
                 escape=dtime(10, 0), rank_mode="gain_asc"),
    "IRG10": dict(desc="gain_asc + 10:00 open (IC study best corner)",
                  entry_open=dtime(10, 0), entry_cutoff=dtime(14, 30),
                  escape=dtime(10, 30), rank_mode="gain_asc"),
    # ---- HV run 2 (2026-08-26): the phase hypothesis. Run 1 showed
    # EVERY amihud threshold gains ~the same (+42-47k) AND the inverted
    # control gains too (+22k) -- signature of "trade less in premarket"
    # rather than "trade smarter". Test that directly: skip premarket
    # entries entirely, with and without the post-open veto.
    "HVN0": dict(desc="no premarket entries at all (entry_open 09:30)",
                 entry_open=dtime(9, 30), entry_cutoff=dtime(14, 30),
                 escape=dtime(10, 0)),
    "HVN1": dict(desc="no premarket entries + post-open bar-range veto",
                 entry_open=dtime(9, 30), entry_cutoff=dtime(14, 30),
                 escape=dtime(10, 0), hv_veto={"amihud_cut": 0.24}),
    "HVN2": dict(desc="premarket entries ONLY (control: 07:00-09:30)",
                 entry_open=dtime(7, 0), entry_cutoff=dtime(9, 30),
                 escape=dtime(9, 0)),
    # ---- HV-series (2026-08-25): the honest-pool edge search, run 1.
    # Registered before running. Baseline C37F = -72,673 / 445d / 18-23
    # negm. Pass bar for a REAL edge: both years independently positive,
    # controls fail, adjacency coherent; anything less is reported as-is.
    "HV000": dict(desc="IDENTITY: C37F reproduction (hv machinery off)",
                  entry_cutoff=dtime(14, 30), escape=dtime(10, 0)),
    "HVA12": dict(desc="HV veto: amihud pm cut 0.12 + bar-range post 2.0",
                  entry_cutoff=dtime(14, 30), escape=dtime(10, 0),
                  hv_veto={"amihud_cut": 0.12}),
    "HVA18": dict(desc="HV veto: amihud pm cut 0.18 + post 2.0",
                  entry_cutoff=dtime(14, 30), escape=dtime(10, 0),
                  hv_veto={"amihud_cut": 0.18}),
    "HVA24": dict(desc="HV veto: amihud pm cut 0.24 (calibrated 0.5% "
                       "map) + post 2.0",
                  entry_cutoff=dtime(14, 30), escape=dtime(10, 0),
                  hv_veto={"amihud_cut": 0.24}),
    "HVA36": dict(desc="HV veto: amihud pm cut 0.36 + post 2.0",
                  entry_cutoff=dtime(14, 30), escape=dtime(10, 0),
                  hv_veto={"amihud_cut": 0.36}),
    "HVCS": dict(desc="CONTROL: seeded random veto ~matched rate",
                 entry_cutoff=dtime(14, 30), escape=dtime(10, 0),
                 hv_veto={"amihud_cut": 0.24, "shuffle_rate": 0.6},
                 hv_shuffle=True),
    "HVCI": dict(desc="CONTROL: INVERTED -- veto TIGHT premarket books",
                 entry_cutoff=dtime(14, 30), escape=dtime(10, 0),
                 hv_veto={"amihud_cut": 0.24, "invert": True}),
    "C37F": dict(desc="C37 on the FULL-coverage pool (post-backfill "
                      "benchmark)",
                 entry_cutoff=dtime(14, 30), escape=dtime(10, 0)),
    # ---- CORRECTED LADDER (2026-09-01): exit modes RESOLVED, not
    # inherited. HOLD = flatten only (window-close is the only exit
    # that can print; asserted at run end). PTRAIL = HOLD + the
    # pressure-modulated trail that the mislabeled XH/K configs were
    # actually running. All four ranked configs carry 10bps/side
    # slippage; the R* controls are random picks under IDENTICAL
    # machinery, costs, AND gap allowance (symmetric is_top), keyed
    # by ROTREP replicate. C37F stays untouched as the identity.
    "HOLD1": dict(desc="rank + HOLD-to-flatten, sequential, 10bps",
                  entry_cutoff=dtime(14, 30), escape=dtime(10, 0),
                  slip=0.001, exit_mode="HOLD"),
    "HOLD6": dict(desc="rank + HOLD-to-flatten, 6 concurrent, 10bps",
                  entry_cutoff=dtime(14, 30), escape=dtime(10, 0),
                  slip=0.001, exit_mode="HOLD", topk=6),
    "PTRAIL1": dict(desc="rank + pressure-trail (10/40 from peak), "
                         "sequential, 10bps",
                    entry_cutoff=dtime(14, 30), escape=dtime(10, 0),
                    slip=0.001, exit_mode="PTRAIL"),
    "PTRAIL6": dict(desc="rank + pressure-trail, 6 concurrent, 10bps",
                    entry_cutoff=dtime(14, 30), escape=dtime(10, 0),
                    slip=0.001, exit_mode="PTRAIL", topk=6),
    "RHOLD6": dict(desc="CONTROL: RANDOM 6 + HOLD, 10bps (ROTREP seeds)",
                   entry_cutoff=dtime(14, 30), escape=dtime(10, 0),
                   slip=0.001, exit_mode="HOLD", topk=6, rand=True),
    "RPTRAIL6": dict(desc="CONTROL: RANDOM 6 + pressure-trail, 10bps "
                          "(ROTREP seeds)",
                     entry_cutoff=dtime(14, 30), escape=dtime(10, 0),
                     slip=0.001, exit_mode="PTRAIL", topk=6, rand=True),
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
    # ---- SIBLING RE-VALIDATION ON THE CAUSAL POOL (2026-08-13) ----
    # C37 was chosen by comparing rotation variants on the HINDSIGHT-cut
    # pool, where the margins between siblings were $10-20k on a $780k
    # base -- and the cut itself was later measured at $109k. A
    # distortion that large can reorder a ranking with margins that
    # thin, so the whole family is re-run honestly. Each sibling is run
    # twice: plain (the champion's own definition, NO veto) and with the
    # 2.0% spread veto, since the veto may interact with a different
    # rotation policy than it did with C37's.
    "SB20": dict(desc="rotation, window 12:00 (original R020 default)",
                 entry_cutoff=dtime(12, 0), escape=dtime(10, 0)),
    "SV20": dict(desc="rotation, window 12:00 (original R020 default) + 2% spread veto",
                 entry_cutoff=dtime(12, 0), escape=dtime(10, 0), spread_veto=2.0),
    "SB13": dict(desc="rotation, window 13:00",
                 entry_cutoff=dtime(13, 0), escape=dtime(10, 0)),
    "SV13": dict(desc="rotation, window 13:00 + 2% spread veto",
                 entry_cutoff=dtime(13, 0), escape=dtime(10, 0), spread_veto=2.0),
    "SB21": dict(desc="rotate only after a LOSING ticket",
                 entry_cutoff=dtime(14, 30), escape=dtime(10, 0), on_win="stay"),
    "SV21": dict(desc="rotate only after a LOSING ticket + 2% spread veto",
                 entry_cutoff=dtime(14, 30), escape=dtime(10, 0), on_win="stay", spread_veto=2.0),
    "SB24": dict(desc="rotation restricted to current top-3",
                 entry_cutoff=dtime(14, 30), escape=dtime(10, 0), top=3),
    "SV24": dict(desc="rotation restricted to current top-3 + 2% spread veto",
                 entry_cutoff=dtime(14, 30), escape=dtime(10, 0), top=3, spread_veto=2.0),
    "SB25": dict(desc="stale-pick escape 09:30 instead of 10:00",
                 entry_cutoff=dtime(14, 30), escape=dtime(9, 30)),
    "SV25": dict(desc="stale-pick escape 09:30 instead of 10:00 + 2% spread veto",
                 entry_cutoff=dtime(14, 30), escape=dtime(9, 30), spread_veto=2.0),
    "SBNE": dict(desc="NO stale-pick escape",
                 entry_cutoff=dtime(14, 30)),
    "SVNE": dict(desc="NO stale-pick escape + 2% spread veto",
                 entry_cutoff=dtime(14, 30), spread_veto=2.0),
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
    # POOL HYGIENE (2026-09-01): test symbols, split/relist artifacts
    # and non-equity types dropped -- see plan/pool_hygiene.py. OPT-IN
    # via POOL_HYGIENE=1; default OFF keeps C37F's -72,673 identity.
    if POOL_HYGIENE:
        out = _hygiene().clean(out, date)
    return out


POOL_HYGIENE = _os.environ.get("POOL_HYGIENE") == "1"
_HYG = []


def _hygiene():
    if not _HYG:
        spec = importlib.util.spec_from_file_location(
            "pool_hygiene", ROOT / "plan/pool_hygiene.py")
        m = importlib.util.module_from_spec(spec)
        sys.modules["pool_hygiene"] = m
        spec.loader.exec_module(m)
        _HYG.append(m)
    return _HYG[0]


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
            last = _last
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
        # IR-series (2026-08-27): the IC study found the champion's own
        # ordering key has mean IC -0.0433 (30/30 sign-stable, control
        # bar 0.013) -- C37 ranks BACKWARDS. gain_now (how far a name
        # has ALREADY run at t) is the strongest stable feature, sign
        # NEGATIVE: prefer the LEAST-extended crosser. rank_mode swaps
        # the ordering key only; eligibility, gates, exits, rotation and
        # the ticket schedule are untouched. Strictly causal: gain_now
        # uses last close <= t vs the PRIOR day's close.
        rm = _RANK_MODE[0]
        if rm:
            gain_now = (last / r["pc"] - 1) * 100 if r["pc"] else 0.0
            if rm == "gain_asc":            # least-extended first
                k = (gain_now,)
            elif rm == "gain_desc":         # INVERTED control: must lose
                k = (-gain_now,)
            elif rm == "gain_asc_coil":     # coil group, gain_asc within
                k = (0 if coil >= 0.95 else 1, gain_now)
            else:
                raise ValueError(f"unknown rank_mode {rm}")
            scored.append((k, r))
            continue
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


def _memo_sim(memo, key, fn):
    """Per-day memo for simulate_trades calls. The ranking at time t and
    a ticket's simulation on (symbol, entry_start, budget) do not depend
    on the random replicate, so 30 replicates share them. Returned
    trade dicts are COPIES (callers tag them with ticket/symbol)."""
    if memo is None:
        return fn()
    if key not in memo:
        memo[key] = fn()
    return [dict(x) for x in memo[key]]


def run_day(cands, date, cfg, stats=None, fc=None, rep=None, memo=None):
    _RANK_MODE[0] = cfg.get("rank_mode")
    entry_open = cfg.get("entry_open", dtime(7, 0))
    cutoff = cfg.get("entry_cutoff", dtime(12, 0))
    rotate = cfg.get("rotate", True)
    trades = []
    t = entry_open
    ticket_i = 0
    last_sym, last_pnl = None, 0.0
    # Effective engine kwargs, resolved ONCE per config (exit whitelist
    # applied); callers that bypass run() get the same resolution.
    base_kw = cfg.get("_simkw")
    if base_kw is None:
        base_kw = build_simkw(cfg.get("_id", "?"), cfg, echo=False)
        cfg["_simkw"] = base_kw
    # Random controls: replicate index (ROTREP, default 0) enters the
    # seed, so 30 replicates are 30 different shuffles, not one.
    if rep is None:
        rep = int((_os.environ.get("ROTREP", "0") or "0").split("-")[0]
                  .split(",")[0])
    while ticket_i < len(TICKETS):
        if t >= cutoff:
            break
        # pick at time t (rank order memoized per day: it is the same
        # for every replicate; the list is copied before any shuffle)
        rk = ("rank", t, cfg.get("top"))
        if memo is not None and rk in memo:
            pool = list(memo[rk])
        else:
            pool = rank_at(cands, t, cfg.get("top"), fc)
            if memo is not None:
                memo[rk] = list(pool)
        # SYMMETRIC GAP ALLOWANCE (2026-09-01): the 35% gap7 limit
        # belongs to the RANKED top name. Remember it BEFORE any shuffle
        # so the random arm gets the same allowance on the same symbol
        # (previously the control got it on a random name).
        ranked_top = pool[0]["c"]["symbol"] if pool else None
        if cfg.get("rand"):
            import random as _rnd
            _rnd.Random(f"rc60-{date}-{ticket_i}-{rep}").shuffle(pool)
        pick = None
        if not rotate and last_sym is not None:
            pick = next((r for r in pool
                         if r["c"]["symbol"] == last_sym), None)
        elif cfg.get("on_win") == "stay" and last_sym is not None \
                and last_pnl > 0:
            pick = next((r for r in pool
                         if r["c"]["symbol"] == last_sym), None)
        if pick is None:
            for r in pool:
                if gates_ok(r, r["c"]["symbol"] == ranked_top):
                    pick = r
                    break
        if pick is None:
            t = _step(t)
            continue
        # K-series concurrency: deploy k tickets to the k best ARMABLE
        # names at this same decision point, each its own full ticket
        # (the $100k/day cap and the ticket schedule still bind). The
        # clock then advances past the LAST exit, so capital is never
        # double-counted. topk=None keeps the sequential champion path
        # byte-identical -- K-series is measurement only; live remains
        # ONE position at a time per the user's cash rules.
        topk = cfg.get("topk")
        if topk:
            picks = []
            for r in pool:
                if len(picks) >= topk or ticket_i + len(picks) >= len(TICKETS):
                    break
                if gates_ok(r, r["c"]["symbol"] == ranked_top):
                    picks.append(r)
            if not picks:
                t = _step(t)
                continue
            last_exit = t
            got = False
            for r in picks:
                dfk = r["df"]
                wk = dfk[(dfk.index.time >= entry_open)
                         & (dfk.index.time < EXIT_END)]
                if len(wk) < 20:
                    continue
                kwk = dict(base_kw)
                if cfg.get("slip"):
                    kwk["slippage_bps"] = cfg["slip"] * 1e4
                if r.get("pmh"):
                    kwk["extra_break_high"] = r["pmh"]
                _es, _bud = max(t, r["cross"]), TICKETS[ticket_i]
                trk = _memo_sim(
                    memo, ("sim", r["c"]["symbol"], _es, _bud),
                    lambda: dt.simulate_trades(
                        wk, prev_close=r["pc"], budget=_bud,
                        entry_start=_es, **kwk))
                trk = [x for x in trk if x.get("entry_time") is not None]
                if not trk:
                    continue
                fe = trk[0]["entry_time"]
                grpk = [x for x in trk if x["entry_time"] == fe]
                for x in grpk:
                    x["ticket"] = ticket_i
                    x["symbol"] = r["c"]["symbol"]
                trades += grpk
                ticket_i += 1
                got = True
                ex = max(x["exit_time"] for x in grpk).time()
                if ex > last_exit:
                    last_exit = ex
            t = _step(max(t, last_exit)) if got else _step(t)
            continue
        # simulate ONE ticket on this name from t
        df = pick["df"]
        w = df[(df.index.time >= entry_open) & (df.index.time < EXIT_END)]
        if len(w) < 20:
            t = _step(t)
            continue
        esc = cfg.get("escape")
        kw = dict(base_kw)
        if cfg.get("slip"):
            kw["slippage_bps"] = cfg["slip"] * 1e4   # engine kwarg name
        if pick.get("pmh"):
            kw["extra_break_high"] = pick["pmh"]   # champion parity:
            # the premarket-high stop-buy travels OUTSIDE the sim dict
        _es, _bud = max(t, pick["cross"]), TICKETS[ticket_i]
        tr = _memo_sim(
            memo, ("sim", pick["c"]["symbol"], _es, _bud),
            lambda: dt.simulate_trades(
                w, prev_close=pick["pc"], budget=_bud,
                entry_start=_es, **kw))
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
        # HV-series (2026-08-25): calibrated-instrument veto on the
        # honest pool. Phase-split per plan/calibrate_liquidity.py:
        # premarket books are measured by AMIHUD (bar-range is ANTI-
        # correlated there, rho -0.34) with undefined = width evidence
        # = VETO; post-open keeps the bar-range proxy at the V200 cap.
        hv = cfg.get("hv_veto")
        if hv:
            import importlib.util as _ilu
            if "liqest" not in sys.modules:
                _sp = _ilu.spec_from_file_location(
                    "liqest", ROOT / "plan/liquidity_estimators.py")
                _m = _ilu.module_from_spec(_sp)
                sys.modules["liqest"] = _m
                _sp.loader.exec_module(_m)
            liq = sys.modules["liqest"]
            if stats is not None:
                stats["checked"] = stats.get("checked", 0) + 1
            _veto = False
            if cfg.get("hv_shuffle"):
                import random as _r
                _veto = _r.Random(f"hv-{date}-{pick['c']['symbol']}-"
                                  f"{ticket_i}").random() < hv.get(
                                      "shuffle_rate", 0.5)
            elif first_entry.time() < dtime(9, 30):
                a = liq.amihud(df, first_entry, hv.get("lb", 30))
                thr = hv["amihud_cut"]
                wide = (a is None) or (a > thr)
                _veto = (not wide) if hv.get("invert") else wide
            else:
                prox = spread_proxy(df, first_entry,
                                    hv.get("post_lb", 10))
                _veto = (prox is not None
                         and prox > hv.get("post_cap", 2.0))
            if _veto:
                if stats is not None:
                    stats["vetoed"] = stats.get("vetoed", 0) + 1
                t = _step(first_entry.time())
                continue
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


def _shares_est(x, budget, slip):
    """Shares behind one trade leg. FILL-MODEL EPOCH 2026-09-02: the
    engine now exports `shares` on every trade dict, so `deployed` is
    exact. The inversion below is kept only for dumps produced by the
    pre-epoch engine (no `shares` key): it sizes int(budget // entry)
    capped by the volume fraction and inverts pnl = (exit*(1-slip) -
    entry) * shares where the move is large enough to make the cents-
    rounding negligible, else falls back to the budget size. Used only
    for the `deployed` fairness column, never for P&L."""
    if x.get("shares"):
        return int(x["shares"])
    entry, exit_, pnl = x.get("entry") or 0, x.get("exit") or 0, x["pnl"]
    cap = int(budget // entry) if entry > 0 else 0
    den = exit_ * (1 - slip) - entry
    if abs(den) >= 0.03 and pnl:
        est = int(round(pnl / den))
        if 0 < est <= cap * 1.02 + 1:
            return est
    return cap


# Labels the ladder runs on. ROTLABELS overrides (comma list), e.g.
# ROTLABELS=aug2026 for the out-of-sample August pool
# (data/massive/gappers_novol_aug2026.json).
LABELS = tuple((_os.environ.get("ROTLABELS") or "year,y2025").split(","))
DUMP_TRADES = _os.environ.get("ROTTRADES") == "1"


def _reps_from_env(cfg):
    """ROTREP: '7' | '0-29' | '0,3,5' -> replicate list (random configs
    only; ranked configs run once with rep=None)."""
    if not cfg.get("rand"):
        return [None]
    s = _os.environ.get("ROTREP", "0") or "0"
    reps = []
    for part in s.split(","):
        if "-" in part:
            a, b = part.split("-")
            reps += list(range(int(a), int(b) + 1))
        else:
            reps.append(int(part))
    return reps


def run(cfg_id, max_days=None):
    cfg = CFGS[cfg_id]
    cfg["_id"] = cfg_id
    print(f"{cfg_id}: {cfg['desc']}", flush=True)
    cfg["_simkw"] = build_simkw(cfg_id, cfg, echo=True)
    reps = _reps_from_env(cfg)
    if reps != [None]:
        print(f"  replicates: {reps}", flush=True)
    slip = cfg.get("slip") or 0.0

    def key_of(rep):
        # Random controls are keyed by replicate so 30 seeds coexist in
        # one shard file; ranked configs keep their plain id.
        return cfg_id if rep is None else f"{cfg_id}#r{rep}"

    out = {rep: {} for rep in reps}
    dump = {rep: [] for rep in reps}
    for lab in LABELS:
        byday = px.load_by_day(lab, 50, "novol")
        st = {rep: dict(stats={}, total=0.0, days=0,
                        monthly=defaultdict(float), daily=[],
                        reasons=defaultdict(lambda: [0, 0.0]),
                        deployed=0.0, tickets=0) for rep in reps}
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
            memo = {}      # rank order + sims shared across replicates
            for rep in reps:
                s = st[rep]
                tr = run_day(cands, date, cfg, s["stats"], fc,
                             rep=rep, memo=memo)
                if not tr:
                    continue
                p = sum(x["pnl"] for x in tr)
                s["total"] += p
                s["days"] += 1
                s["monthly"][date[:7]] += p
                tk = {x.get("ticket") for x in tr}
                s["tickets"] += len(tk)
                s["daily"].append((date, p, len(tk)))
                for x in tr:
                    cat = exit_category(x.get("reason"))
                    s["reasons"][cat][0] += 1
                    s["reasons"][cat][1] += x["pnl"]
                    sh = _shares_est(x, TICKETS[x.get("ticket", 0)], slip)
                    s["deployed"] += sh * (x.get("entry") or 0)
                    if DUMP_TRADES:
                        dump[rep].append({
                            "label": lab, "date": date,
                            "symbol": x.get("symbol"),
                            "ticket": x.get("ticket"),
                            "entry_time": str(x.get("entry_time")),
                            "entry": x.get("entry"),
                            "exit_time": str(x.get("exit_time")),
                            "exit": x.get("exit"),
                            "reason": x.get("reason"), "pnl": x["pnl"],
                            "shares": sh, "peak_pct": x.get("peak_pct")})
            if n % 50 == 0:
                s0 = st[reps[0]]
                print(f"  ..{lab} {n}/{len(items)} "
                      f"({s0['days']}d ${s0['total']:+,.0f})", flush=True)
        for rep in reps:
            s = st[rep]
            total, days, monthly, daily = (s["total"], s["days"],
                                           s["monthly"], s["daily"])
            reasons, deployed, tickets = (s["reasons"], s["deployed"],
                                          s["tickets"])
            res_key = key_of(rep)
            negm = sum(1 for v in monthly.values() if v < 0)
            print(f" {res_key} {lab:<6} {days:>4}d ${total:>+12,.0f} "
                  f"{negm}/{len(monthly)}  maxDD ${out_dd(daily):>9,.0f}  "
                  f"[{cfg['desc']}]", flush=True)
            # EXIT-REASON DECOMPOSITION (2026-09-01): a HOLD config must
            # show window-close ONLY. Anything else = an exit leaked in.
            rline = "  ".join(f"{k}:{v[0]}/${v[1]:+,.0f}"
                              for k, v in sorted(reasons.items()))
            print(f"   exits [{res_key} {lab}]: {rline}", flush=True)
            if cfg.get("exit_mode") == "HOLD":
                assert set(reasons) <= {"window-close"}, (
                    f"{cfg_id}: HOLD config printed non-flatten exits: "
                    f"{dict(reasons)}")
            vch = s["stats"].get("checked", 0)
            vvt = s["stats"].get("vetoed", 0)
            if vch:
                print(f"   veto: {vvt}/{vch} entries blocked "
                      f"({100*vvt/vch:.1f}%)", flush=True)
            # RISK COLUMNS (2026-08-13). Total P&L and negative months
            # alone cannot distinguish edge from leverage -- the
            # S-campaign learned that when pressure-scaled sizing "won"
            # purely by deploying more capital.
            eq = pk = dd = 0.0
            for _, pnl, _ in daily:
                eq += pnl
                pk = max(pk, eq)
                dd = max(dd, pk - eq)
            wins = sum(1 for _, pnl, _ in daily if pnl > 0)
            tks = [t for _, _, t in daily]
            # FAIR-COMPARISON COLUMNS (2026-09-01): totals were compared
            # across 1x vs 6x capital. Return on deployed capital and
            # P&L per ticket are the like-for-like numbers; ex-best
            # strips the single largest day so one outlier cannot carry
            # a verdict.
            best = max(daily, key=lambda d: d[1], default=None)
            best_day = round(best[1]) if best else 0
            worst_day = round(min((p for _, p, _ in daily), default=0))
            m_ex = dict(monthly)
            if best:
                m_ex[best[0][:7]] -= best[1]
            negm_ex_best = sum(1 for v in m_ex.values() if v < 0)
            fair = {"deployed": round(deployed), "tickets": tickets,
                    "ret_on_deployed_pct": (round(100 * total / deployed, 3)
                                            if deployed else None),
                    "pnl_per_ticket": (round(total / tickets, 1)
                                       if tickets else None),
                    "best_day": best_day,
                    "best_day_date": best[0] if best else None,
                    "worst_day": worst_day,
                    "total_ex_best": round(total - (best[1] if best else 0)),
                    "negm_ex_best": negm_ex_best}
            print(f"   fair  [{res_key} {lab}]: tickets {tickets} deployed "
                  f"${deployed:,.0f} ret {fair['ret_on_deployed_pct']}% "
                  f"per_ticket ${fair['pnl_per_ticket']} best {best_day:+,} "
                  f"({fair['best_day_date']}) worst {worst_day:+,} "
                  f"ex_best {fair['total_ex_best']:+,} negm_ex_best "
                  f"{negm_ex_best}/{len(monthly)}", flush=True)
            out[rep][lab] = {
                "total": round(total), "days": days, "negm": negm,
                "nmonths": len(monthly),
                "veto_checked": vch, "veto_blocked": vvt,
                "max_dd": round(dd),
                "max_dd_pct_of_peak": (round(100 * dd / pk, 1)
                                       if pk > 0 else None),
                "win_days_pct": (round(100 * wins / len(daily), 1)
                                 if daily else None),
                "tickets_per_day_avg": (round(sum(tks) / len(tks), 2)
                                        if tks else None),
                **fair,
                "exit_reasons": {k: {"n": v[0], "pnl": round(v[1])}
                                 for k, v in sorted(reasons.items())},
                "monthly": {k: round(v) for k, v in
                            sorted(monthly.items())}}
    res = json.loads(RES_F.read_text()) if RES_F.exists() else {}
    for rep in reps:
        res[key_of(rep)] = {
            "desc": cfg["desc"], "rep": rep,
            "exit_mode": cfg.get("exit_mode"),
            "pool_hygiene": POOL_HYGIENE,
            "halal_strict": _os.environ.get("HALAL_STRICT") == "1",
            "labels": list(LABELS), **out[rep]}
    RES_F.write_text(json.dumps(res, indent=1))
    if DUMP_TRADES:
        for rep in reps:
            tf = ROOT / ("data/massive/rotation_trades_"
                         f"{key_of(rep).replace('#', '-')}_"
                         f"{_SHARD or 'main'}.json")
            tf.write_text(json.dumps(dump[rep]))
            print(f"  trades -> {tf.name} ({len(dump[rep])} legs)",
                  flush=True)
    return out[reps[0]] if len(reps) == 1 else out


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
