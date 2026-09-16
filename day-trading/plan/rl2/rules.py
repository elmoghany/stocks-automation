"""RL-SERIES v2, APPROACH 4 (2026-09-16): rule discovery by search.

Random + genetic search over INTERPRETABLE rules:

    entry   a conjunction of 1..3 tests  feature[j] {<,>} threshold
            (thresholds are quantiles of that feature measured on TRAIN
            ROWS ONLY, so the grid itself carries no test information)
  x window  entries allowed only between two minutes of the session
  x exit    a fixed horizon, or stop / take / trailing / time-stop

Scored by total P&L through the SAME simulator every other approach uses.

DISCIPLINE
  * search fold-by-fold: for test month M the search sees only dates < M.
  * a separate HELD-OUT FINAL YEAR run: the search sees 2024-10-22 ..
    2025-07-31 and nothing else, and its single best rule is then run once
    over 2025-08-01 .. 2026-08-06. Best-on-train and out-of-sample are
    reported as two different numbers, because the first is a maximum over
    N_CAND draws and is therefore biased upward by construction.
  * the search is screened on a SUBSAMPLE of train days for speed and the
    survivors are re-scored on the full train set; both stages use train
    days only.
"""
import json
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import dataset as DS                                          # noqa: E402
import features as FT                                         # noqa: E402
import sim as SM                                              # noqa: E402

FEAT = HERE / "out" / "feat"
RES = HERE / "results"

N_CAND = 900          # random candidates per generation
N_GEN = 3             # generations (elitist mutation)
N_ELITE = 40
SCREEN_DAYS = 90      # train days used to screen a candidate
MIN_TICKETS = 150     # a rule that trades less than this on train is noise

EXITS = ([("horizon", h) for h in (15, 30, 60, 120)]
         + [("flatten",)]
         + [("rule", {"stop": s, "take": tk, "trail": tr, "tmax": tm})
            for s in (0.02, 0.04, None) for tk in (0.02, 0.05, None)
            for tr in (0.03, None) for tm in (60, 240, None)
            if not (s is None and tk is None and tr is None and tm is None)])


class Cand:
    __slots__ = ("tests", "win", "exit")

    def __init__(self, tests, win, exit_):
        self.tests, self.win, self.exit = tests, win, exit_

    def score_matrix(self, day):
        F = day.F
        ok = np.ones(F.shape[:2], bool)
        for j, sgn, thr in self.tests:
            ok &= (F[:, :, j] > thr) if sgn > 0 else (F[:, :, j] < thr)
        lo, hi = self.win
        wm = (FT.STEPS >= lo) & (FT.STEPS <= hi)
        ok &= wm[:, None]
        return np.where(ok, 1.0, -np.inf)

    def as_dict(self):
        return {"tests": [[FT.FEATURE_NAMES[j], ">" if s > 0 else "<",
                           round(float(t), 5)] for j, s, t in self.tests],
                "window": [int(self.win[0]), int(self.win[1])],
                "exit": (list(self.exit) if self.exit[0] != "rule"
                         else ["rule", self.exit[1]])}


def quantile_grid(X, qs=(0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95)):
    return np.quantile(X, qs, axis=0)


def sample(rng, grid, nq):
    k = rng.integers(1, 4)
    js = rng.choice(grid.shape[1], size=k, replace=False)
    tests = [(int(j), int(rng.choice([-1, 1])),
              float(grid[rng.integers(0, nq), j])) for j in js]
    lo = int(rng.choice([0, 240, 330, 390, 450]))
    hi = int(rng.choice([720, 780, 840, 930]))
    return Cand(tests, (lo, max(hi, lo + 60)), EXITS[rng.integers(0, len(EXITS))])


def mutate(rng, c, grid, nq):
    tests = [list(t) for t in c.tests]
    what = rng.integers(0, 4)
    if what == 0 and tests:
        i = rng.integers(0, len(tests))
        tests[i][2] = float(grid[rng.integers(0, nq), tests[i][0]])
    elif what == 1 and tests:
        i = rng.integers(0, len(tests))
        tests[i][1] = -tests[i][1]
    elif what == 2 and len(tests) < 3:
        j = int(rng.choice(grid.shape[1]))
        tests.append([j, int(rng.choice([-1, 1])),
                      float(grid[rng.integers(0, nq), j])])
    elif what == 3 and len(tests) > 1:
        tests.pop(int(rng.integers(0, len(tests))))
    win = c.win
    ex = c.exit
    if rng.random() < 0.3:
        win = (int(rng.choice([0, 240, 330, 390, 450])),
               int(rng.choice([720, 780, 840, 930])))
        win = (win[0], max(win[1], win[0] + 60))
    if rng.random() < 0.3:
        ex = EXITS[rng.integers(0, len(EXITS))]
    return Cand([tuple(t) for t in tests], win, ex)


def evaluate(c, days):
    trades = []
    for d in days:
        trades += SM.run_day(d, c.score_matrix(d), c.exit,
                             max_new_per_step=2)[0]
    return trades


def search(train_days_all, grid, seed=0, log=print):
    rng = np.random.default_rng(seed)
    nq = grid.shape[0]
    idx = rng.choice(len(train_days_all),
                     size=min(SCREEN_DAYS, len(train_days_all)), replace=False)
    screen = [train_days_all[i] for i in idx]
    pop = [sample(rng, grid, nq) for _ in range(N_CAND)]
    best = None
    for g in range(N_GEN):
        scored = []
        for c in pop:
            tr = evaluate(c, screen)
            n = len(tr)
            s = sum(t["pnl"] for t in tr) if n >= MIN_TICKETS * len(screen) \
                / max(len(train_days_all), 1) else -1e18
            scored.append((s, c))
        scored.sort(key=lambda x: -x[0])
        elite = [c for _, c in scored[:N_ELITE]]
        log(f"    gen{g}: best screen ${scored[0][0]:,.0f}")
        best = elite[0]
        pop = elite + [mutate(rng, elite[rng.integers(0, len(elite))], grid, nq)
                       for _ in range(N_CAND - N_ELITE)]
    # confirm the elite on the FULL train set
    final = []
    for c in elite:
        tr = evaluate(c, train_days_all)
        if len(tr) < MIN_TICKETS:
            continue
        final.append((sum(t["pnl"] for t in tr), len(tr), c))
    final.sort(key=lambda x: -x[0])
    return (final[0][2], final[0][0], final[0][1]) if final else (best, 0.0, 0)


def month_end(m):
    y, mm = int(m[:4]), int(m[5:])
    return f"{y+1}-01-01" if mm == 12 else f"{y}-{mm+1:02d}-01"


def main():
    a = sys.argv[1:]
    seed = int(a[a.index("--seed") + 1]) if "--seed" in a else 0
    mode = a[a.index("--mode") + 1] if "--mode" in a else "holdout"
    RES.mkdir(parents=True, exist_ok=True)
    dates = sorted(p.stem for p in FEAT.glob("*.npz"))
    R = DS.Rows()

    def grid_for(lo_excl):
        m = R.date_of_row < lo_excl
        return quantile_grid(R.X[m])

    def load(ds):
        return [SM.Day(FEAT / f"{d}.npz") for d in ds]

    t0 = time.time()
    out = {"seed": seed, "mode": mode}
    if mode == "holdout":
        TR_END, TE_END = "2025-08-01", "2026-08-07"
        tr_d = [d for d in dates if d < TR_END]
        te_d = [d for d in dates if TR_END <= d < TE_END]
        print(f"holdout: search on {len(tr_d)} train days, "
              f"evaluate once on {len(te_d)} held-out days", flush=True)
        grid = grid_for(TR_END)
        best, s_tr, n_tr = search(load(tr_d), grid, seed)
        tr_sum = SM.summarize(evaluate(best, load(tr_d)), len(tr_d), "train")
        te_sum = SM.summarize(evaluate(best, load(te_d)), len(te_d), "heldout")
        out.update(rule=best.as_dict(), train=tr_sum, heldout=te_sum)
        print("BEST RULE:", json.dumps(best.as_dict()), flush=True)
        print("train   :", json.dumps(tr_sum), flush=True)
        print("heldout :", json.dumps(te_sum), flush=True)
    else:                                   # walk-forward monthly
        import bandit as BD
        rows = []
        all_tr = []
        for m in BD.TEST_MONTHS:
            lo, hi = f"{m}-01", month_end(m)
            tr_d = [d for d in dates if d < lo]
            te_d = [d for d in dates if lo <= d < hi]
            if len(tr_d) < 60 or not te_d:
                continue
            grid = grid_for(lo)
            best, s_tr, n_tr = search(load(tr_d), grid, seed,
                                      log=lambda *_: None)
            tr = evaluate(best, load(te_d))
            all_tr += tr
            s = SM.summarize(tr, len(te_d), m)
            s["rule"] = best.as_dict()
            s["train_total"] = round(s_tr, 2)
            rows.append(s)
            print(f"  {m}: {s['tickets']} tkts ${s['total']:,.0f} "
                  f"{s['per_ticket']:+.2f}/tkt (train ${s_tr:,.0f})", flush=True)
        nd = len([d for d in dates if d >= f"{BD.TEST_MONTHS[0]}-01"])
        out["walkforward"] = SM.summarize(all_tr, nd, "RULES-wf")
        out["per_month"] = rows
        print("walk-forward:", json.dumps(out["walkforward"]), flush=True)
    out["wall_s"] = round(time.time() - t0, 1)
    f = RES / f"rules_{mode}_s{seed}.json"
    f.write_text(json.dumps(out, indent=1))
    print("wrote", f, flush=True)


if __name__ == "__main__":
    main()
