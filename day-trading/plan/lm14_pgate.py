"""LEGACY-14: entry pressure as a GATE / SIZE on top of R4 (coil order).
pressure30 at the decision grid minute is causal (feature grid). A gated
name is skipped and the next coil-ranked name is tried (cp_sim's own
order[:8] loop). Sizing doubles the ticket when the gate passes.
Usage: python lm14_pgate.py out.json"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cp_run as R                                          # noqa: E402
import cp_lib as L                                          # noqa: E402
import cp_feat as F                                         # noqa: E402

S = R.S
S.TICKETS = [10_000.0] * 7
_orig = S._try_ticket


def _patched(day, Fd, i, t, gi, budget, cfg, cost):
    thr = cfg.get("pthr")
    if thr is not None:
        p = Fd["pressure30"][i, gi]
        ok = np.isfinite(p) and p >= thr
        if cfg.get("pinv"):
            ok = not ok
        if cfg.get("pmode") == "gate" and not ok:
            return None
        if cfg.get("pmode") == "size" and ok:
            budget = budget * 2.0
    return _orig(day, Fd, i, t, gi, budget, cfg, cost)


S._try_ticket = _patched
base = dict(rank="coil", stop_pct=None)
jobs = {
    "R4": (S.default_cfg(**base), None, None),
    "PGATE30": (S.default_cfg(pthr=0.30, pmode="gate", **base), None, None),
    "PGATE15": (S.default_cfg(pthr=0.15, pmode="gate", **base), None, None),
    "PGATE30inv": (S.default_cfg(pthr=0.30, pmode="gate", pinv=True, **base), None, None),
    "PSIZE30": (S.default_cfg(pthr=0.30, pmode="size", **base), None, None),
}
OOS = len(sys.argv) > 2 and sys.argv[2] == "oos"
ds = R.dates(oos=OOS)
if OOS:
    jobs = {k: jobs[k] for k in ("R4", "PSIZE30")}
out = S.run_many(ds, jobs)
for k in out:
    for x in out[k]:
        for kk, vv in list(x.items()):
            if isinstance(vv, (np.floating, np.integer)):
                x[kk] = float(vv)
Path(sys.argv[1]).write_text(json.dumps({"ndays": len(ds), "legs": out}, default=float))
print({k: len(v) for k, v in out.items()})
