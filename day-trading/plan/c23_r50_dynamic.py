"""TRUE dynamic R50 backtest of C23 (user 2026-08-05): the slot starts
at $15k and each traded day adds HALF of that day's P&L to the slot
(slot = 15k + 0.5 x max(0, cumulative P&L); base never shrinks).
Unlike the tier-interpolated estimate, every day is simulated AT its
actual slot, so the 20%-of-10-min-volume cap bites exactly as it
would live. Runs the two backtest years chronologically
(Oct24-Jul25 then Aug25-Jul26) carrying the slot across the boundary.
Writes data/massive/c23_r50_curve.json (per-day slot/pnl/cum)."""

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "plan"))
_spec = importlib.util.spec_from_file_location(
    "penny_x100", ROOT / "plan" / "penny_x100.py")
x = importlib.util.module_from_spec(_spec)
sys.modules["penny_x100"] = x
_spec.loader.exec_module(x)

BASE = 15_000.0
STATE = {"cum": 0.0, "curve": []}
_orig = x.sim_window


def wrapper(w, c, spec, sub=None):
    slot = BASE + 0.5 * max(0.0, STATE["cum"])
    spec.setdefault("sim", {})["budget"] = slot
    tr = _orig(w, c, spec, sub)
    pnl = sum(t["pnl"] for t in tr)
    STATE["cum"] += pnl
    if len(w):
        STATE["curve"].append(dict(date=str(w.index[0].date()),
                                   slot=round(slot), pnl=round(pnl, 2),
                                   cum=round(STATE["cum"], 2)))
    return tr


x.sim_window = wrapper

SPEC = dict(id="C23R50", desc="C23 dynamic half-reinvest", pm_break=True,
            exit_1pm=True,
            sim=dict(orb_bars=5, max_vol_frac=0.20, vol_frac_window=10,
                     pressure_trail=(10, 0.30, 0.30, 10, 40),
                     scale_out_pressure_skip=0.30, wick_guard=3.0))

marks = {}
for label in ("y2025", "year"):      # chronological order
    start_cum = STATE["cum"]
    out = x.run_experiment(dict(SPEC), label)
    yr = STATE["cum"] - start_cum
    marks[label] = yr
    print(f"{label}: year P&L ${yr:+,.0f} | cum ${STATE['cum']:+,.0f} "
          f"| slot now ${BASE + 0.5 * max(0, STATE['cum']):,.0f}",
          flush=True)

curve = STATE["curve"]
(ROOT / "data/massive/c23_r50_curve.json").write_text(json.dumps(curve))
peak = dd = 0.0
for r in curve:
    peak = max(peak, r["cum"])
    dd = min(dd, r["cum"] - peak)
neg = [r for r in curve if r["pnl"] < 0]
print(f"\nDYNAMIC R50 2yr: ${STATE['cum']:+,.0f} "
      f"(flat-15k was +$992,866)")
print(f"max slot ${max(r['slot'] for r in curve):,} | "
      f"max drawdown ${dd:+,.0f} | worst day "
      f"${min(r['pnl'] for r in curve):+,.0f} | "
      f"{len(neg)}/{len(curve)} negative days")
