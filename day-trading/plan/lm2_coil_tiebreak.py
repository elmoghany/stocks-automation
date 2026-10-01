"""LEGACY-2: does R4's coil edge survive a CAUSAL tie-break?

cp_sim.rank_key('coil') sorts by -coil with a STABLE argsort, so ties
(several names exactly at their running high, coil == 1.0) are broken by
ARRAY INDEX. The panel's array order is the gapper-pool file order, which
is correlated (Spearman ~ -0.4..-0.5) with FULL-DAY volume -- hindsight.
This re-runs R4 with the tie broken (a) randomly, (b) by REVERSED index,
(c) by causal dollar volume so far (desc), (d) by causal dvol ascending,
and counts how often the top coil was a tie. No edits to cp_sim: the
rank key is wrapped.
"""
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cp_lib as L                                          # noqa: E402
import cp_feat as F                                         # noqa: E402
import cp_sim as S                                          # noqa: E402
import lm2_coil_engine as E                                 # noqa: E402

_orig = S.rank_key
STATE = {"rng": np.random.default_rng(7)}


def rank_key(Fd, gi, cfg):
    r = cfg["rank"]
    if not r.startswith("coil_"):
        return _orig(Fd, gi, cfg)
    coil = np.nan_to_num(Fd["coil"][:, gi].astype(np.float64), nan=0.0)
    n = len(coil)
    q = np.round(coil, 5)                    # ties at the running high
    if r == "coil_rand":
        tb = STATE["rng"].random(n)
    elif r == "coil_revidx":
        tb = -np.arange(n) / n
    elif r == "coil_dvol_hi":
        dv = np.nan_to_num(Fd["dvol_now"][:, gi].astype(np.float64))
        tb = -np.argsort(np.argsort(dv)) / n
    elif r == "coil_dvol_lo":
        dv = np.nan_to_num(Fd["dvol_now"][:, gi].astype(np.float64))
        tb = np.argsort(np.argsort(dv)) / n
    elif r == "coil_idx":
        tb = np.arange(n) / n
    else:
        raise ValueError(r)
    return -q + 1e-7 * tb


S.rank_key = rank_key


def main():
    J = {}
    for nm in ["coil_idx", "coil_revidx", "coil_dvol_hi", "coil_dvol_lo"]:
        J[nm] = (dict(rank=nm, stop_pct=None), None, None)
    for k in range(5):
        J[f"coil_rand{k}"] = (dict(rank="coil_rand", stop_pct=None, seed=k), None, None)
    out = {k: [] for k in J}
    ties = []
    t0 = time.time()
    for n, date in enumerate(F.dates()):
        Fd = F.load(date)
        day = L.load_day(date)
        if Fd is None or day is None:
            continue
        el = Fd["elig_last"]
        for gi in range(1, 61):
            c = np.round(np.nan_to_num(Fd["coil"][el[:, gi], gi], nan=0.0), 5)
            if len(c):
                ties.append(int((c == c.max()).sum()))
        for key, (over, _, _) in J.items():
            STATE["rng"] = np.random.default_rng(hash((key, date)) % 2**31)
            for leg in S.run_day(day, Fd, S.default_cfg(**over), None):
                out[key].append(dict(date=date, sym=leg["sym"],
                                     em=leg["entry_min"], xm=leg["exit_min"],
                                     entry=leg["entry"], exit=leg["exit"],
                                     sh=leg["shares"], gross=leg["gross"],
                                     reason=leg["reason"]))
        if n % 100 == 0:
            print(n, date, f"{time.time() - t0:.0f}s", flush=True)
    t = np.array(ties)
    print(f"decision minutes: top-coil tie count median {np.median(t):.0f}, "
          f"share with >=2 tied at the top {np.mean(t >= 2):.2%}, "
          f">=5 {np.mean(t >= 5):.2%}")
    (E.OUT / "tiebreak.json").write_text(json.dumps(out, default=float))
    E.summarize({k: v for k, v in out.items()})


if __name__ == "__main__":
    main()
