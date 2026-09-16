"""RL-SERIES v2 (2026-09-16): the null distribution for approach 4.

A rule search reports a MAXIMUM over thousands of candidates, so "the best
rule on train made $X out of sample" means nothing until you know what an
UNSEARCHED rule of the same shape makes out of sample. Two nulls:

  1. `--mode draws` : N_DRAW rules sampled from the same generator, with
     thresholds taken from TRAIN quantiles, each evaluated directly on the
     held-out year. Gives the distribution of out-of-sample $/ticket for a
     rule nobody selected, and the searched rule's percentile in it.
  2. `--mode matched` : random-ENTRY controls (uniform scores, same
     eligibility / fills / costs / exit rule) tuned to the searched rule's
     ticket RATE, 30 seeds. Answers "does the rule beat random entries
     that trade as rarely as it does".
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import dataset as DS                                          # noqa: E402
import features as FT                                         # noqa: E402
import rules as RU                                            # noqa: E402
import sim as SM                                              # noqa: E402

FEAT = HERE / "out" / "feat"
RES = HERE / "results"
TR_END, TE_END = "2025-08-01", "2026-08-07"
N_DRAW = 1500
MIN_TICKETS_OOS = 60


def main():
    a = sys.argv[1:]
    mode = a[a.index("--mode") + 1] if "--mode" in a else "draws"
    dates = sorted(p.stem for p in FEAT.glob("*.npz"))
    te_d = [d for d in dates if TR_END <= d < TE_END]
    days = [SM.Day(FEAT / f"{d}.npz") for d in te_d]
    out = {"mode": mode, "heldout_days": len(days)}

    if mode == "draws":
        R = DS.Rows()
        grid = RU.quantile_grid(R.X[R.date_of_row < TR_END])
        rng = np.random.default_rng(12345)
        pts, tots = [], []
        for i in range(N_DRAW):
            c = RU.sample(rng, grid, grid.shape[0])
            tr = RU.evaluate(c, days)
            if len(tr) < MIN_TICKETS_OOS:
                continue
            s = SM.summarize(tr, len(days))
            pts.append(s["per_ticket"])
            tots.append(s["total"])
            if (i + 1) % 250 == 0:
                print(f"  {i+1}/{N_DRAW} kept={len(pts)}", flush=True)
        pts = np.array(pts)
        tots = np.array(tots)
        out.update(n_draws=N_DRAW, n_kept=int(len(pts)),
                   per_ticket={"mean": round(float(pts.mean()), 2),
                               "sd": round(float(pts.std(ddof=1)), 2),
                               "p50": round(float(np.percentile(pts, 50)), 2),
                               "p90": round(float(np.percentile(pts, 90)), 2),
                               "p95": round(float(np.percentile(pts, 95)), 2),
                               "p99": round(float(np.percentile(pts, 99)), 2),
                               "max": round(float(pts.max()), 2),
                               "frac_positive": round(float((pts > 0).mean()), 4)},
                   total={"mean": round(float(tots.mean()), 0),
                          "p95": round(float(np.percentile(tots, 95)), 0),
                          "max": round(float(tots.max()), 0)})
        for f in sorted(RES.glob("rules_holdout_s*.json")):
            r = json.loads(f.read_text())
            v = r["heldout"]["per_ticket"]
            out.setdefault("searched", {})[f.stem] = {
                "heldout_per_ticket": v,
                "heldout_total": r["heldout"]["total"],
                "percentile_in_null": round(float((pts < v).mean()) * 100, 2)}
    else:
        import honesty as HO
        for rate in (0.5, 1.0, 1.2, 2.0):
            p = rate / (FT.T * 60.0)          # ~ per (step, name) probability
            r = HO.random_control(days, seeds=30, exit_rule=("horizon", 180),
                                  p_entry=p, max_new=2,
                                  label=f"RANDOM-rate{rate}")
            out[f"rate_{rate}"] = {k: v for k, v in r.items() if k != "rows"}
            print(rate, out[f"rate_{rate}"], flush=True)
    f = RES / f"rules_null_{mode}.json"
    f.write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))
    print("wrote", f, flush=True)


if __name__ == "__main__":
    main()
