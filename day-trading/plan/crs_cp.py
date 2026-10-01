"""COST-RESCORE (2026-10-01): CHAMPION-REPLAY R5 (coil rank, start 10:00,
stop -2%) + its 30-seed random control in R5's own frame (cp_run.recomb:
rank none, rand, seed k), re-run ONCE with NO cost callable, dumping every
leg's gross so it can be priced at any per-side bps (cp_sim FLAT_BPS
convention: b on entry and exit notional). R4's legs are re-used from
PESSIMISM-AUDIT's identical dump (pa_out/cp_r4_legs.json). Identity: the
dump's net_flat totals are compared with data/massive/cp/recomb.json.
Writes plan/crs_cp_r5_legs.json."""
import json, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cp_run as R
import cp_lib as L
S = R.S
t0 = time.time()
ds = R.dates()
best = dict(rank="coil", t_start=L.mgrid(10, 0), stop_pct=0.02)
jobs = {"R5": (S.default_cfg(**best), None, None)}
for k in range(30):
    jobs[f"RND{k}"] = (S.default_cfg(**dict(best, rank="none", rand=True, seed=k)), None, None)
legs = S.run_many(ds, jobs, progress=True)
keep = ("date", "sym", "entry_min", "exit_min", "entry", "exit", "shares", "gross", "net_flat", "reason")
out = {"ndays": len(ds), "dates": ds,
       "legs": {k: [{kk: v[kk] for kk in keep} for v in Lg] for k, Lg in legs.items()},
       "secs": time.time() - t0}
(HERE / "crs_cp_r5_legs.json").write_text(json.dumps(out, default=float))
print("done", round(time.time() - t0), len(legs["R5"]))
