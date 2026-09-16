"""RL-SERIES v2 (2026-09-16): the mechanical baselines every approach is
measured against, on the FULL 255-day test window.

A random control that fills all seven tickets in the first premarket minute
is not a fair opponent -- it loses to the 120 bps extended round trip, not
to a lack of information. These baselines separate the two:

  RANDOM-ANY      uniform scores, entries allowed anywhere on the grid,
                  greedy to the cap (this is what "random" meant in v1)
  RANDOM-SPREAD   uniform scores with a per-(step, name) entry probability,
                  so the seven tickets land across the day
  RANDOM-RTH      the same, but entries confined to 09:30-16:00 -- the
                  "no information, but obeys the session rule" opponent,
                  which is the one that actually matters
  HOLD            never trade

30 seeds each, same eligibility / fills / costs / exit rule.
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import features as FT                                         # noqa: E402
import sim as SM                                              # noqa: E402

FEAT = HERE / "out" / "feat"
RES = HERE / "results"
TEST_LO, TEST_HI = "2025-08-01", "2026-08-07"
SEEDS = 30


def main():
    dates = sorted(p.stem for p in FEAT.glob("*.npz"))
    te = [d for d in dates if TEST_LO <= d < TEST_HI]
    days = [SM.Day(FEAT / f"{d}.npz") for d in te]
    rth = (FT.STEPS >= FT.RTH_LO) & (FT.STEPS < FT.RTH_HI)
    out = {"test_days": len(days)}

    sc0 = [np.full((FT.T, d.S), -np.inf) for d in days]
    tr, _ = [], None
    trades = []
    for d, s in zip(days, sc0):
        trades += SM.run_day(d, s)[0]
    out["HOLD"] = SM.summarize(trades, len(days), "HOLD")

    specs = [("RANDOM-ANY", None, -np.inf, SM.MAX_TICKETS),
             ("RANDOM-SPREAD", None, 1.0 - 0.005, 2),
             ("RANDOM-RTH", rth, 1.0 - 0.02, 2),
             ("RANDOM-RTH-greedy", rth, -np.inf, SM.MAX_TICKETS)]
    for label, mask, thr, mx in specs:
        rows = []
        for s in range(SEEDS):
            tr = []
            for d in days:
                rng = np.random.default_rng(20_000 + s)
                sc = rng.random((FT.T, d.S))
                if mask is not None:
                    sc = np.where(mask[:, None], sc, -np.inf)
                tr += SM.run_day(d, sc, ("horizon", 30), min_score=thr,
                                 max_new_per_step=mx)[0]
            rows.append(SM.summarize(tr, len(days), f"{label}-s{s}"))
        pt = np.array([r["per_ticket"] for r in rows])
        tot = np.array([r["total"] for r in rows])
        out[label] = {
            "seeds": SEEDS,
            "mean_per_ticket": round(float(pt.mean()), 3),
            "min_per_ticket": round(float(pt.min()), 3),
            "max_per_ticket": round(float(pt.max()), 3),
            "sd_per_ticket": round(float(pt.std(ddof=1)), 3),
            "mean_total": round(float(tot.mean()), 2),
            "min_total": round(float(tot.min()), 2),
            "max_total": round(float(tot.max()), 2),
            "mean_tickets_per_day": round(
                float(np.mean([r["tickets_per_day"] for r in rows])), 2),
            "mean_sharpe": round(float(np.mean([r["sharpe"] for r in rows])), 3),
            "mean_ext_exit_n": round(
                float(np.mean([r["ext_exit_n"] for r in rows])), 1),
            "mean_rth_exit_n": round(
                float(np.mean([r["rth_exit_n"] for r in rows])), 1),
        }
        print(label, json.dumps(out[label]), flush=True)
    (RES / "baselines.json").write_text(json.dumps(out, indent=1))
    print("wrote", RES / "baselines.json")


if __name__ == "__main__":
    main()
