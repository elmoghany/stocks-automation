"""RL-SERIES v2, ITERATION PASS for approach 4 (2026-09-16).

Same search as plan/rl2/rules.py with three changes, each justified by
TRAIN-visible evidence only, and scored against the STANDING LOOP BAR:

  1. ENTRIES ARE CONFINED TO 09:30-16:00. Justification is the TRAIN half of
     the unconditional table (extended-hours entries lose $174/ticket at
     every horizon on TRAIN), so this uses no test information. The first
     pass wasted most of its candidate budget rediscovering it.
  2. BIGGER BUDGET: 1,500 candidates x 4 generations, elite 60.
  3. WALK-FORWARD MONTHLY as well as held-out, over the extended
     2025-02 .. 2026-08 window, so "both years positive" has an answer and
     the result is 19 independent out-of-sample months rather than one.

Everything else -- train-quantile thresholds, screening on a train
subsample, the single best-on-train rule evaluated ONCE out of sample -- is
unchanged.

  python plan/rl2/rules2.py --mode holdout --seed 0
  python plan/rl2/rules2.py --mode wf --seed 0
"""
import json
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import bandit2 as B2                                          # noqa: E402
import bar as BAR                                             # noqa: E402
import dataset as DS                                          # noqa: E402
import features as FT                                         # noqa: E402
import rules as RU                                            # noqa: E402
import sim as SM                                              # noqa: E402

FEAT = HERE / "out" / "feat"
RES = HERE / "results"

N_CAND = 1500
N_GEN = 4
N_ELITE = 60
SCREEN_DAYS = 90
MIN_TICKETS = 150
RTH_LO, RTH_HI = FT.RTH_LO, FT.RTH_HI
LO_CHOICES = [RTH_LO, RTH_LO + 30, RTH_LO + 60, RTH_LO + 120]
HI_CHOICES = [RTH_LO + 120, RTH_LO + 240, RTH_HI - 60, RTH_HI]
EXITS = RU.EXITS


def sample(rng, grid, nq):
    k = rng.integers(1, 4)
    js = rng.choice(grid.shape[1], size=k, replace=False)
    tests = [(int(j), int(rng.choice([-1, 1])),
              float(grid[rng.integers(0, nq), j])) for j in js]
    lo = int(rng.choice(LO_CHOICES))
    hi = int(max(rng.choice(HI_CHOICES), lo + 60))
    return RU.Cand(tests, (lo, hi), EXITS[rng.integers(0, len(EXITS))])


def mutate(rng, c, grid, nq):
    d = RU.mutate(rng, c, grid, nq)
    lo = int(min(max(d.win[0], RTH_LO), RTH_HI - 60))
    hi = int(min(max(d.win[1], lo + 60), RTH_HI))
    return RU.Cand(d.tests, (lo, hi), d.exit)


def search(train_days, grid, seed, log=print):
    rng = np.random.default_rng(seed)
    nq = grid.shape[0]
    idx = rng.choice(len(train_days), size=min(SCREEN_DAYS, len(train_days)),
                     replace=False)
    screen = [train_days[i] for i in idx]
    floor = MIN_TICKETS * len(screen) / max(len(train_days), 1)
    pop = [sample(rng, grid, nq) for _ in range(N_CAND)]
    elite = pop[:N_ELITE]
    for g in range(N_GEN):
        scored = []
        for c in pop:
            tr = RU.evaluate(c, screen)
            s = sum(t["pnl"] for t in tr) if len(tr) >= floor else -1e18
            scored.append((s, c))
        scored.sort(key=lambda x: -x[0])
        elite = [c for _, c in scored[:N_ELITE]]
        log(f"    gen{g}: best screen ${scored[0][0]:,.0f}")
        pop = elite + [mutate(rng, elite[rng.integers(0, len(elite))], grid, nq)
                       for _ in range(N_CAND - N_ELITE)]
    final = []
    for c in elite:
        tr = RU.evaluate(c, train_days)
        if len(tr) >= MIN_TICKETS:
            final.append((sum(t["pnl"] for t in tr), c))
    final.sort(key=lambda x: -x[0])
    return (final[0][1], final[0][0]) if final else (elite[0], 0.0)


def main():
    a = sys.argv[1:]
    mode = a[a.index("--mode") + 1] if "--mode" in a else "holdout"
    seed = int(a[a.index("--seed") + 1]) if "--seed" in a else 0
    RES.mkdir(parents=True, exist_ok=True)
    dates = sorted(p.stem for p in FEAT.glob("*.npz"))
    R = DS.Rows()
    step_mask = (FT.STEPS >= RTH_LO) & (FT.STEPS < RTH_HI)

    def grid_for(lo):
        return RU.quantile_grid(R.X[R.date_of_row < lo])

    def load(ds):
        return [SM.Day(FEAT / f"{d}.npz") for d in ds]

    t0 = time.time()
    out = {"mode": mode, "seed": seed}
    if mode == "holdout":
        TR_END, TE_END = "2025-08-01", "2026-08-07"
        tr_d = [d for d in dates if d < TR_END]
        te_d = [d for d in dates if TR_END <= d < TE_END]
        best, s_tr = search(load(tr_d), grid_for(TR_END), seed)
        tr_m = BAR.metrics(RU.evaluate(best, load(tr_d)), tr_d, "train")
        te_tr = RU.evaluate(best, load(te_d))
        te_m = BAR.metrics(te_tr, te_d, "heldout")
        rc = BAR.random_control(load(te_d), te_d, best.exit,
                                min(0.9, max(1e-5, te_m["tickets_per_day"]
                                             / (FT.T * 60.0) * 8)), 2,
                                seeds=30, step_mask=step_mask, T=FT.T)
        out.update(rule=best.as_dict(), train=tr_m, heldout=te_m,
                   verdict=BAR.verdict(te_m, rc),
                   random_control={k: v for k, v in rc.items()
                                   if k not in ("total", "total_ex_best")})
        print("RULE:", json.dumps(best.as_dict()), flush=True)
        print("train  :", json.dumps(tr_m), flush=True)
        print("heldout:", json.dumps(te_m), flush=True)
        print("verdict:", json.dumps(out["verdict"]), flush=True)
    else:
        rows, all_tr = [], []
        for m in B2.TEST_MONTHS:
            lo, hiD = f"{m}-01", B2.month_end(m)
            tr_d = [d for d in dates if d < lo]
            te_d = [d for d in dates if lo <= d < hiD]
            if len(tr_d) < 60 or not te_d:
                continue
            best, s_tr = search(load(tr_d), grid_for(lo), seed,
                                log=lambda *_: None)
            tr = RU.evaluate(best, load(te_d))
            all_tr += tr
            mm = BAR.metrics(tr, te_d, m)
            mm["rule"] = best.as_dict()
            mm["train_total"] = round(s_tr, 2)
            rows.append(mm)
            print(f"  {m}: {mm['tickets']:4d} tkt ${mm['total']:>9,.0f} "
                  f"{mm['per_ticket']:+8.2f}/tkt (train ${s_tr:,.0f})",
                  flush=True)
        te_all = [d for d in dates if f"{B2.TEST_MONTHS[0]}-01" <= d
                  < B2.month_end(B2.TEST_MONTHS[-1])]
        mtot = BAR.metrics(all_tr, te_all, "RULES2-wf")
        rc = BAR.random_control(load(te_all), te_all, ("horizon", 30),
                                min(0.9, max(1e-5, mtot["tickets_per_day"]
                                             / (FT.T * 60.0) * 8)), 2,
                                seeds=30, step_mask=step_mask, T=FT.T)
        out.update(walkforward=mtot, per_month=rows,
                   verdict=BAR.verdict(mtot, rc),
                   random_control={k: v for k, v in rc.items()
                                   if k not in ("total", "total_ex_best")})
        print("walk-forward:", json.dumps(mtot), flush=True)
        print("verdict:", json.dumps(out["verdict"]), flush=True)
    out["wall_s"] = round(time.time() - t0, 1)
    f = RES / f"rules2_{mode}_s{seed}.json"
    f.write_text(json.dumps(out, indent=1))
    print("wrote", f, flush=True)


if __name__ == "__main__":
    main()
