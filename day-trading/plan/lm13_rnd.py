"""LEGACY-13 step 5: the path-free test of a RANGE GATE. R4's 30-seed
random control (same frame, same exits, random pick among eligible names)
re-run for 10 seeds with the decision minute captured, so each random
leg carries sigma1 (and the up30 score where one exists) AT ITS DECISION
MINUTE. ~11k honest legs answer "is a ticket on a high-range name worth
more than one on a low-range name" without R4's five-leg path luck.
Writes plan/lm13_rnd_legs.json."""
import json
import time

import numpy as np

import lm13_lib as M

S, F, L = M.S, M.F, M.L
t0 = time.time()
ds = M.r4_dates()
sc = M.load_scores()
cfgs = {k: S.default_cfg(rank="none", rand=True, stop_pct=None, seed=k)
        for k in range(10)}
out = []
for n, d in enumerate(ds):
    Fd = F.load(d)
    day = L.load_day(d)
    if Fd is None or day is None:
        continue
    for k, cfg in cfgs.items():
        for leg in S.run_day(day, Fd, cfg):
            i, gi = leg["i"], leg["gi"]
            out.append(dict(
                seed=k, date=d, sym=leg["sym"], t=leg["t"],
                entry_min=leg["entry_min"], exit_min=leg["exit_min"],
                ret=leg["exit"] / leg["entry"] - 1,
                notional=leg["shares"] * leg["entry"],
                reason=leg["reason"].split()[0],
                sigma1=float(Fd["sigma1"][i, gi]),
                dvol_now=float(Fd["dvol_now"][i, gi]),
                last=float(Fd["last"][i, gi]),
                score=M.score_at(sc.get(d), leg["sym"], leg["t"]),
                mfe_mae=M.fwd(day, i, leg["entry_min"], leg["entry"])))
    if (n + 1) % 100 == 0:
        print(n + 1, len(out), round(time.time() - t0), flush=True)
json.dump(out, open(M.PLAN / "lm13_rnd_legs.json", "w"), default=float)
print("done", len(out), round(time.time() - t0))
