"""RL-SERIES v2, APPROACH 1 (2026-09-16): contextual bandit / supervised
policy.

At every decision minute a gradient-boosted regressor predicts the NET
return of the trade a $15k ticket opened there would realize over a fixed
horizon; the policy buys the highest-predicted names that clear a
threshold. This is the lowest-variance way to ask "is there anything in
the causal features at all" -- no exploration, no credit assignment, no
seed lottery beyond the boosting seed.

WALK-FORWARD, STRICTLY
  For each test month M in TEST_MONTHS: train on every row whose date is
  < the first day of M, predict M, never look at M again. Feature
  normalization is irrelevant to trees, but the target's own scale is
  taken from train rows only. No hyperparameter is tuned on any test
  month; PARAMS below are fixed before the first run and never touched.

VARIANTS (identical code path, only the training label differs)
  real        the true net return
  shuffled    the target permuted across (name, t) rows WITHIN each day
              -- per-row sums are not preserved, so the only thing
              destroyed is the association between a row's features and
              its own outcome. A positive out-of-sample result here is
              proof of leakage. (v1's control permuted the price path
              instead and was shown to be a Brownian bridge artifact.)
  foresight   the model is replaced by the realized net return itself.
              Must be strongly positive or the harness has no power.

Usage:
  python plan/rl2/bandit.py --horizon 30 [--variant real] [--seed 0]
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

OUT = HERE / "out"
FEAT = OUT / "feat"
RES = HERE / "results"

TEST_MONTHS = ["2025-08", "2025-09", "2025-10", "2025-11", "2025-12",
               "2026-01", "2026-02", "2026-03", "2026-04", "2026-05",
               "2026-06", "2026-07", "2026-08"]

PARAMS = dict(objective="regression", metric="l2", learning_rate=0.05,
              num_leaves=63, min_data_in_leaf=500, feature_fraction=0.8,
              bagging_fraction=0.8, bagging_freq=1, lambda_l2=1.0,
              verbosity=-1, num_threads=4)
NROUND = 400
LAST_ENTRY_MIN = 19 * 60 + 30 - 4 * 60        # 19:30 ET
MAX_NEW_PER_STEP = 2
MIN_PRED = 0.0        # buy only when the model predicts a positive NET return


def month_end(m):
    y, mm = int(m[:4]), int(m[5:])
    return f"{y+1}-01-01" if mm == 12 else f"{y}-{mm+1:02d}-01"


def shuffle_within_day(y, d, seed):
    rng = np.random.default_rng(seed)
    out = y.copy()
    order = np.argsort(d, kind="stable")
    ds = d[order]
    bnd = np.flatnonzero(np.diff(ds)) + 1
    for a, b in zip(np.r_[0, bnd], np.r_[bnd, len(ds)]):
        idx = order[a:b]
        out[idx] = y[rng.permutation(idx)]
    return out


def run(horizon_idx, variant="real", seed=0, exit_rule=None, tag=""):
    import lightgbm as lgb
    H = FT.HORIZONS[horizon_idx]
    if exit_rule is None:
        exit_rule = ("flatten",) if H >= 10 ** 5 else ("horizon", H)
    R = DS.Rows()
    y_all = R.Y[:, horizon_idx].astype(np.float64)
    ok_all = R.OKY[:, horizon_idx]
    last_entry_step = int(np.searchsorted(FT.STEPS, LAST_ENTRY_MIN, "right") - 1)

    per_month, all_trades, models = [], [], []
    for m in TEST_MONTHS:
        lo, hi = f"{m}-01", month_end(m)
        tr = (R.date_of_row < lo) & ok_all
        te_dates = [d for d in R.dates if lo <= d < hi]
        if not te_dates or tr.sum() < 10_000:
            continue
        ytr = y_all[tr]
        if variant == "shuffled":
            ytr = shuffle_within_day(ytr, R.D[tr], seed + 991)
        if variant == "foresight":
            booster = None
        else:
            ds = lgb.Dataset(R.X[tr], label=ytr, free_raw_data=True)
            p = dict(PARAMS)
            p["seed"] = seed
            p["bagging_seed"] = seed + 1
            p["feature_fraction_seed"] = seed + 2
            booster = lgb.train(p, ds, num_boost_round=NROUND)
        mt = []
        for d in te_dates:
            day = SM.Day(FEAT / f"{d}.npz")
            sc = np.full((FT.T, day.S), -np.inf, np.float64)
            t_i, s_i = np.nonzero(day.printed)
            if not len(t_i):
                continue
            if variant == "foresight":
                pr = np.where(day.tgt_ok[t_i, s_i, horizon_idx],
                              day.tgt[t_i, s_i, horizon_idx], -1e9)
            else:
                pr = booster.predict(day.F[t_i, s_i])
            sc[t_i, s_i] = pr
            mt += SM.run_day(day, sc, exit_rule, min_score=MIN_PRED,
                             max_new_per_step=MAX_NEW_PER_STEP,
                             last_entry_step=last_entry_step)[0]
        s = SM.summarize(mt, len(te_dates), m)
        s["train_rows"] = int(tr.sum())
        per_month.append(s)
        all_trades += mt
        models.append((m, booster))
        print(f"  {m}: {s['tickets']} tickets  ${s['total']:,.0f}  "
              f"{s['per_ticket']:+.2f}/tkt  sharpe {s['sharpe']}", flush=True)

    ndays = len({t["date"] for t in all_trades}) or 1
    n_test_days = len([d for d in R.dates
                       if f"{TEST_MONTHS[0]}-01" <= d < month_end(TEST_MONTHS[-1])])
    tot = SM.summarize(all_trades, n_test_days,
                       f"BANDIT-{variant}-h{H}-s{seed}{tag}")
    tot["per_month"] = per_month
    tot["horizon"] = H
    tot["variant"] = variant
    tot["seed"] = seed
    tot["exit_rule"] = list(map(str, exit_rule))
    tot["min_pred"] = MIN_PRED
    if models and models[-1][1] is not None:
        imp = models[-1][1].feature_importance("gain")
        tot["feature_gain"] = sorted(
            [[FT.FEATURE_NAMES[i], round(float(imp[i]), 1)]
             for i in range(len(imp))], key=lambda x: -x[1])[:12]
    del ndays
    return tot, all_trades


def main():
    a = sys.argv[1:]
    H = int(a[a.index("--horizon") + 1]) if "--horizon" in a else 30
    variant = a[a.index("--variant") + 1] if "--variant" in a else "real"
    seed = int(a[a.index("--seed") + 1]) if "--seed" in a else 0
    hi = FT.HORIZONS.index(H)
    RES.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    tot, trades = run(hi, variant, seed)
    tot["wall_s"] = round(time.time() - t0, 1)
    f = RES / f"bandit_{variant}_h{H}_s{seed}.json"
    f.write_text(json.dumps(tot, indent=1))
    print(json.dumps({k: v for k, v in tot.items()
                      if k not in ("per_month", "feature_gain")}, indent=1))
    print("wrote", f, flush=True)


if __name__ == "__main__":
    main()
