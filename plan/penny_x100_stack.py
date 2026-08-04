"""X100 stacking round: greedy composites of PASS winners, both years.
Reuses penny_x100.run_experiment. Results -> x100_results_comp.json.
CLI: --ids C01,C02  (default: all)
"""

import importlib.util
import json
import sys
from datetime import time as dtime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
ARGS = sys.argv[1:]
_spec = importlib.util.spec_from_file_location(
    "x100", ROOT / "plan" / "penny_x100.py")
x = importlib.util.module_from_spec(_spec)
sys.argv = [sys.argv[0]]           # neutralize flags for x100 module load
_spec.loader.exec_module(x)

RES = ROOT / "data" / "massive" / "x100_results_comp.json"

COMPOSITES = [
    # C01: the three clean both-year sizing/entry winners stacked
    dict(id="C01", desc="orb5 + vol_frac 0.20 + window 10min",
         sim=dict(orb_bars=5, max_vol_frac=0.20, vol_frac_window=10)),
    # C02: C01 + premarket-high extra trigger
    dict(id="C02", desc="C01 + pm-high stop-buy", pm_break=True,
         sim=dict(orb_bars=5, max_vol_frac=0.20, vol_frac_window=10)),
    # C03: C01 + premarket-$vol ranking (Y2-strong candidate)
    dict(id="C03", desc="C01 + rank by premarket $vol", rank="pm_dvol",
         sim=dict(orb_bars=5, max_vol_frac=0.20, vol_frac_window=10)),
    # C04: theoretical ceiling -- C01 with the cap removed entirely
    dict(id="C04", desc="orb5 + UNCAPPED size (ceiling, fill-realism!)",
         sim=dict(orb_bars=5, max_vol_frac=None)),
    # C05: C01 stress-tested with 10bps/side slippage
    dict(id="C05", desc="C01 + slippage 10bps stress",
         sim=dict(orb_bars=5, max_vol_frac=0.20, vol_frac_window=10,
                  slippage_bps=10.0)),
    # C06: C01 + exits until 1PM (requires user sign-off on window)
    dict(id="C06", desc="C01 + exits to 1PM [NEEDS SIGN-OFF]",
         exit_1pm=True,
         sim=dict(orb_bars=5, max_vol_frac=0.20, vol_frac_window=10)),
    # C07: the C02 winner under 10bps/side slippage stress
    dict(id="C07", desc="C02 + slippage 10bps stress", pm_break=True,
         sim=dict(orb_bars=5, max_vol_frac=0.20, vol_frac_window=10,
                  slippage_bps=10.0)),
]


def main():
    ids = None
    for i, a in enumerate(ARGS):
        if a == "--ids" and i + 1 < len(ARGS):
            ids = ARGS[i + 1].split(",")
    res = json.loads(RES.read_text()) if RES.exists() else {}
    for spec in COMPOSITES:
        if ids and spec["id"] not in ids:
            continue
        for label in ("year", "y2025"):
            key = f"{spec['id']}|{label}"
            if key in res:
                continue
            out = x.run_experiment(dict(spec), label)
            res = json.loads(RES.read_text()) if RES.exists() else {}
            res[key] = out
            RES.write_text(json.dumps(res))
            print(f"{spec['id']:>4} {label:<6} {out['days']:>4}d "
                  f"${out['total']:>+11,} {out['negm']}/{out['nmonths']}  "
                  f"[{spec['desc']}]", flush=True)


if __name__ == "__main__":
    main()
