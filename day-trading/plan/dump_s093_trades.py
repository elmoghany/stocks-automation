"""Dump per-trade detail for S093 (C23 rules + exit window to 15:00) so
per-pattern economics can be re-measured UNDER THAT WINDOW -- pattern
P&L under a 1PM flatten need not hold when exits run to 3PM.
Writes data/massive/s093_trades_{label}.json (same shape as the C23 dump).
"""

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

SPEC = dict(x.BYID["S093"])          # C23 rules + exit_end=(15, 0)

for label in ("year", "y2025"):
    DUMP.clear()
    out = x.run_experiment(dict(SPEC), label)
    f = ROOT / f"data/massive/s093_trades_{label}.json"
    f.write_text(json.dumps(DUMP))
    print(f"{label}: {out['days']}d ${out['total']:+,} -> {f.name} "
          f"({sum(len(d['trades']) for d in DUMP)} trades)", flush=True)
