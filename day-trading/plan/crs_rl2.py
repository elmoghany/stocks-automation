"""COST-RESCORE (2026-10-01): RL-SCOUT v2 approach 4 seed 0 (the published
held-out rule, rl2/results/rules_holdout_s0.json) + the 30-seed rate-matched
random control, exactly as cr_rerun.stage_rl2 builds them (imported, not
reimplemented). The rl2 path is cost-free (proved by cr_engine.
assert_path_cost_free), so each leg's GROSS = sh*(px_out-px_in) is dumped
with its ext flags and re-priced at any b in crs_rescore (ext legs keep
+50 bps, cr_engine.reprice flat convention). Writes plan/crs_rl2_legs.json."""
import json, sys, time
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cr_rerun as CR
r2 = HERE / "rl2"
sys.path.insert(0, str(r2))
FT = CR._load("features", r2 / "features.py")
SM = CR._load("sim", r2 / "sim.py")
RL = CR._load("rules", r2 / "rules.py")
TR_END, TE_END = "2025-08-01", "2026-08-07"
t0 = time.time()
paths = sorted((r2 / "out" / "feat").glob("*.npz"))
hold = [SM.Day(p_) for p_ in paths if TR_END <= p_.stem < TE_END]
best = json.loads((r2 / "results" / "rules_holdout_s0.json").read_text())
rd = best["rule"]
tests = [(FT.FEATURE_NAMES.index(n), 1 if op == ">" else -1, float(v)) for n, op, v in rd["tests"]]
cand = RL.Cand(tests, tuple(rd["window"]),
               (rd["exit"][0], rd["exit"][1]) if len(rd["exit"]) > 1 else (rd["exit"][0],))
KEEP = ("date", "sym", "m_in", "m_out", "px_in", "px_out", "sh", "ext_in", "ext_out", "pnl")
cl = lambda trs: [{k: (x[k].item() if hasattr(x[k], "item") else x[k]) for k in KEEP} for x in trs]  # noqa: E731
legs = {"RULE": cl(RL.evaluate(cand, hold))}
rate = len(legs["RULE"]) / max(len(hold), 1)
p_entry = rate / (SM.T * 1.0)
for s_ in range(30):
    trs = []
    for d in hold:
        rng = np.random.default_rng(10_000 + s_)
        sc = rng.random((SM.T, d.S))
        trs += SM.run_day(d, sc, cand.exit, min_score=1.0 - p_entry, max_new_per_step=2)[0]
    legs[f"RND{s_}"] = cl(trs)
    print(s_, len(trs), round(time.time() - t0), flush=True)
(HERE / "crs_rl2_legs.json").write_text(json.dumps(
    {"dates": [d.date for d in hold] if hasattr(hold[0], "date") else [p.stem for p in paths if TR_END <= p.stem < TE_END],
     "rule": rd, "published": best["heldout"], "legs": legs, "secs": time.time() - t0}, default=str))
print("done", len(legs["RULE"]))
