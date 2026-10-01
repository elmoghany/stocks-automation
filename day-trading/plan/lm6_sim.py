"""LEGACY-6: honest re-sims of R4 restricted by the entry-time features the
anatomy pass flagged, each with its OWN random control (same filter, same
exits, random pick).  Uses cp_sim unchanged; the filter is applied by
wrapping run_day so Fd['elig_last'] is AND-ed with a causal mask built from
the cp_feat grid (value at grid m uses bars <= m / prior sessions only).

Cost per leg: measured half-spread at entry and exit (cp_cost.TapeCost with
the impact term switched off, trailing window excludes the fill minute)
+ 4 bps/side (PESSIMISM-AUDIT's gapper guidance), and a flat 15 bps/side.
All $ are re-based to a $10k ticket by return (ret * 10,000).
"""
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(r"C:\cornell\stocks-automation\day-trading")
sys.path.insert(0, str(ROOT / "plan"))
import cp_run as R                                          # noqa: E402
import cp_cost as CC                                        # noqa: E402

S = R.S
_orig = S.run_day


def _filt_run_day(day, Fd, cfg, cost=None):
    f = cfg.get("filt")
    if f is None:
        return _orig(day, Fd, cfg, cost)
    Fd2 = dict(Fd)
    with np.errstate(invalid="ignore"):
        Fd2["elig_last"] = Fd["elig_last"] & f(Fd)
    return _orig(day, Fd2, cfg, cost)


S.run_day = _filt_run_day


def col(Fd, k):
    return np.broadcast_to(Fd[k][:, None], Fd["elig_last"].shape)


FILTS = {
    "ALL": None,
    "ILLIQ": lambda F: ~(col(F, "dvol60") >= 1e6),          # <$1M/day or no history
    "LIQ": lambda F: col(F, "dvol60") >= 1e6,
    "SIGHI": lambda F: F["sigma1"] >= 0.0135,
    "SIGLO": lambda F: ~(F["sigma1"] >= 0.0135),
    "ILLIQ_SIGHI": lambda F: ~(col(F, "dvol60") >= 1e6) & (F["sigma1"] >= 0.0135),
    "LIQ_SIGHI": lambda F: (col(F, "dvol60") >= 1e6) & (F["sigma1"] >= 0.0135),
}
NSEED = 10


def main():
    ds = R.dates()
    tc = CC.TapeCost(coef=0.0)

    def hs(day, i, m, px, sh):
        return tc.dollars(day, i, m, px, sh)

    jobs = {}
    for k, f in FILTS.items():
        jobs[k] = (dict(S.default_cfg(rank="coil", stop_pct=None), filt=f), hs, None)
        for s in range(NSEED):
            jobs[f"{k}|RND{s}"] = (dict(S.default_cfg(rank="none", rand=True,
                                                      stop_pct=None, seed=s),
                                        filt=f), hs, None)
    t0 = time.time()
    legs = S.run_many(ds, jobs, progress=True)
    keep = ("date", "sym", "entry_min", "exit_min", "entry", "exit", "shares",
            "gross", "cost_meas", "reason")
    out = {"ndays": len(ds), "secs": time.time() - t0,
           "legs": {k: [{kk: v[kk] for kk in keep} for v in L] for k, L in legs.items()}}
    (ROOT / "plan/lm6_out/sim_legs.json").write_text(json.dumps(out, default=float))
    print("done", time.time() - t0, {k: len(v) for k, v in legs.items() if "|" not in k})


if __name__ == "__main__":
    main()
