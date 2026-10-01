"""COST-RESCORE (2026-10-01): VS2 `W8RSd` (green-on-red, entries 09:35-14:30,
hold to the flatten) + a 30-seed gate-matched random control (`rs_rand`:
same market-red gate, same minutes, random name), re-run ONCE at the
published 10 bps/side with every leg dumped. W8RSd never had a 30-seed
control and never had a leg dump, so this is the one re-run the line needs.

Cost convention of day-trading.simulate_trades: `entry` already carries
(1+slip), `exit` is raw, pnl = (exit*(1-slip) - entry)*shares. trail_pct=999 /
stop_pct=99 / no target means no exit level depends on the cost, so
re-pricing at any b is exact: fill = entry/(1+0.001),
net(b) = (exit*(1-b) - fill*(1+b))*shares. All entries >= 09:35, flatten
<= 15:00: no extended-hours leg (asserted in crs_rescore).

Writes plan/crs_vs2_legs.json. vs2_wide's own results file is redirected
to the scratchpad so no shared file is touched.
"""
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
os.environ["VS2W_SHARD"] = "crs"
import importlib.util  # noqa: E402

spec = importlib.util.spec_from_file_location("vs2_wide", HERE / "vs2_wide.py")
VW = importlib.util.module_from_spec(spec)
sys.modules["vs2_wide"] = VW
spec.loader.exec_module(VW)

SCR = Path(os.environ.get("CRS_SCRATCH", str(HERE)))
VW.RES_F = SCR / "crs_vs2_results_scratch.json"
_a, _b = os.environ.get("CRS_SEEDS", "0-29").split("-")
SEEDS = list(range(int(_a), int(_b) + 1))
NSEED = len(SEEDS)
TAG = os.environ.get("CRS_TAG", "all")
WITH_RULE = os.environ.get("CRS_RULE", "1") == "1"

base = VW.CFGS["W8RSd"]
ctl = dict(base, rank="rs_rand", desc="CRS control: gate kept, random name, hold")
VW.CFGS["W8RSd-G"] = ctl

_orig_reps = VW.reps_for
VW.reps_for = lambda cfg: (SEEDS if cfg is ctl else _orig_reps(cfg))

LEGS = {}
_orig_run_day = VW.run_day
KEEP = ("date", "symbol", "ticket", "entry_time", "exit_time", "entry", "exit",
        "shares", "pnl", "reason")


def run_day(cands, date, cfg, rep, cache):
    tr = _orig_run_day(cands, date, cfg, rep, cache)
    key = "W8RSd" if cfg is base else f"RND{rep}"
    for x in tr:
        d = {k: x.get(k) for k in KEEP}
        d["date"] = date
        for k in ("entry_time", "exit_time"):
            d[k] = str(d[k])
        LEGS.setdefault(key, []).append(d)
    return tr


VW.run_day = run_day
t0 = time.time()
VW.main((["W8RSd"] if WITH_RULE else []) + ["W8RSd-G"], int(os.environ.get("CRS_DAYS", "0")) or None)
alld = sorted(set(VW.dates_for("wy1")) | set(VW.dates_for("wy2")))
(HERE / f"crs_vs2_legs_{TAG}.json").write_text(json.dumps(
    {"dates": alld, "slip_bps": VW.SLIP_BPS, "seeds": SEEDS, "legs": LEGS,
     "secs": time.time() - t0}, default=str))
print("done", round(time.time() - t0), {k: len(v) for k, v in LEGS.items()}.get("W8RSd"))
