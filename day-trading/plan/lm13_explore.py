"""LEGACY-13 step 1: R4 at $10k tickets, every leg annotated with the
causal range forecasts at its decision minute and (diagnosis only) its
forward MFE/MAE to 15:00. Writes plan/lm13_base_legs.json."""
import json
import time

import numpy as np

import lm13_lib as M

S, F, L = M.S, M.F, M.L
t0 = time.time()
ds = M.r4_dates()
sc = M.load_scores()
cfg = S.default_cfg(rank="coil", stop_pct=None)
out = []
for n, d in enumerate(ds):
    Fd = F.load(d)
    day = L.load_day(d)
    if Fd is None or day is None:
        continue
    for leg in S.run_day(day, Fd, cfg):
        i, gi = leg["i"], leg["gi"]
        rec = {k: leg[k] for k in ("sym", "entry_min", "exit_min", "entry",
                                   "exit", "shares", "gross", "reason",
                                   "t", "ticket")}
        rec["date"] = d
        for k in M.FEATS:
            a = Fd[k]
            rec[k] = float(a[i, gi] if a.ndim == 2 else a[i])
        rec["score"] = M.score_at(sc.get(d), leg["sym"], leg["t"])
        rec["mfe"], rec["mae"] = M.fwd(day, i, leg["entry_min"], leg["entry"])
        out.append(rec)
    if (n + 1) % 100 == 0:
        print(n + 1, len(out), round(time.time() - t0), flush=True)
json.dump({"ndays": len(ds), "legs": out},
          open(M.PLAN / "lm13_base_legs.json", "w"), default=float)
print("done", len(out), json.dumps(M.summ(out, len(ds)), default=float))
