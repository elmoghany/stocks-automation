"""One-off: re-run C23 capturing per-trade detail (for the artifact's
rich table columns), by wrapping penny_x100.sim_window. Writes
data/massive/c23_trades_{label}.json in the same shape as the C21
dumps (per-day records with a trades list)."""

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent))
sys.path.insert(0, str(ROOT / "plan"))
_spec = importlib.util.spec_from_file_location(
    "penny_x100", ROOT / "plan" / "penny_x100.py")
x = importlib.util.module_from_spec(_spec)
sys.modules["penny_x100"] = x
_spec.loader.exec_module(x)

DUMP = []
_orig = x.sim_window


def wrapper(w, c, spec, sub=None):
    tr = _orig(w, c, spec, sub)
    if len(w):
        DUMP.append(dict(
            date=str(w.index[0].date()), symbol=c["symbol"],
            prev_close=c.get("prev_close"),
            pnl=round(sum(t["pnl"] for t in tr), 2),
            trades=[{k: (str(v) if "time" in k else v)
                     for k, v in t.items()} for t in tr]))
    return tr


x.sim_window = wrapper

SPEC = dict(id="C23dump", desc="C23 trades dump", pm_break=True,
            exit_1pm=True,
            sim=dict(orb_bars=5, max_vol_frac=0.20, vol_frac_window=10,
                     pressure_trail=(10, 0.30, 0.30, 10, 40),
                     scale_out_pressure_skip=0.30, wick_guard=3.0))

for label in ("year", "y2025"):
    DUMP.clear()
    out = x.run_experiment(dict(SPEC), label)
    f = ROOT / f"data/massive/c23_trades_{label}.json"
    f.write_text(json.dumps(DUMP))
    print(f"{label}: {out['days']}d ${out['total']:+,} "
          f"-> {f.name} ({sum(len(d['trades']) for d in DUMP)} trades)",
          flush=True)
