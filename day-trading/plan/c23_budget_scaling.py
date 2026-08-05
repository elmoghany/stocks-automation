"""How does C23 scale with slot size? The half-profit-reinvest policy
(user 2026-08-05) grows the slot with cumulative profits, but rule 13
(position <= 20% of trailing 10-min volume) caps fills on thin gappers,
so P&L scales SUBLINEARLY. Rerun C23 at budgets 15k/30k/60k/120k and
report totals + effective scaling to locate the saturation point."""

import importlib.util
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

BASE = dict(pm_break=True, exit_1pm=True,
            sim=dict(orb_bars=5, max_vol_frac=0.20, vol_frac_window=10,
                     pressure_trail=(10, 0.30, 0.30, 10, 40),
                     scale_out_pressure_skip=0.30, wick_guard=3.0))

for b in (30_000, 60_000, 120_000):
    spec = dict(BASE, id=f"C23B{b//1000}")
    spec["sim"] = dict(BASE["sim"], budget=float(b))
    for label in ("year", "y2025"):
        out = x.run_experiment(dict(spec), label)
        lin = (412_879 if label == "year" else 579_988) * b / 15_000
        print(f"budget {b//1000}k {label}: ${out['total']:+,} "
              f"({out['days']}d, negm {out['negm']}) | linear would be "
              f"${lin:+,.0f} -> capture {100*out['total']/lin:.0f}%",
              flush=True)
