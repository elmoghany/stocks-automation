"""RL-SERIES v2, ITERATION PASS (2026-09-16): the same contextual-bandit
machinery as plan/rl2/bandit.py, but swept over the three levers that the
first pass said were binding, and scored against the STANDING LOOP BAR
(plan/rl2/bar.py) rather than against -$0.00/ticket.

What the first pass established, and what each lever is for:

  * The unconditional expectancy is ~ -$33/ticket in the regular session and
    ~ -$170/ticket outside it, and the model's top three features by gain
    were `is_ext`, `tod` and `min_to_1600`. The model was spending its whole
    capacity learning a clock.
    -> `--rth 1` removes extended-hours rows from TRAINING and extended-hours
       minutes from the ENTRY grid, so the model has to learn something else.
  * The raw net-return target is dominated by a common (day, minute) factor
    -- the whole universe moves together -- which a cross-sectional selector
    cannot trade.
    -> `--target xs` demeans the target across the names PRINTING at the same
       (day, minute). The policy is then a pure relative-value ranker. This
       is causal: the demeaning uses only rows at that same minute.
    -> `--target sign` is the same question as a classifier.
  * A fixed horizon throws away the exit.
    -> `--exit trail:STOP,TAKE,TRAIL,TMAX` runs the bandit's entries through
       the TA exit ladder the rule search preferred.

Walk-forward is unchanged and strict: for test month M, train on every row
dated before M. The buy threshold is a quantile of the model's predictions on
its OWN TRAINING ROWS, so no test information reaches it. The test window is
extended back to 2025-02 (19 months, ~375 days) so that "both years positive"
is a question with an answer.

  python plan/rl2/bandit2.py --rth 1 --target xs --q 0.99 --horizon 30
"""
import json
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import bar as BAR                                             # noqa: E402
import dataset as DS                                          # noqa: E402
import features as FT                                         # noqa: E402
import sim as SM                                              # noqa: E402

FEAT = HERE / "out" / "feat"
RES = HERE / "results"

TEST_MONTHS = ["2025-02", "2025-03", "2025-04", "2025-05", "2025-06",
               "2025-07", "2025-08", "2025-09", "2025-10", "2025-11",
               "2025-12", "2026-01", "2026-02", "2026-03", "2026-04",
               "2026-05", "2026-06", "2026-07", "2026-08"]
PARAMS = dict(objective="regression", metric="l2", learning_rate=0.05,
              num_leaves=63, min_data_in_leaf=500, feature_fraction=0.8,
              bagging_fraction=0.8, bagging_freq=1, lambda_l2=1.0,
              verbosity=-1, num_threads=4)
NROUND = 400
RTH_LAST_ENTRY = 15 * 60 + 55 - 4 * 60          # 15:55 ET
ANY_LAST_ENTRY = 19 * 60 + 30 - 4 * 60          # 19:30 ET


def month_end(m):
    y, mm = int(m[:4]), int(m[5:])
    return f"{y+1}-01-01" if mm == 12 else f"{y}-{mm+1:02d}-01"


def xs_demean(y, d, t, ok):
    """Demean the target across the names printing at the same (day, minute).

    Causal: every row in a group shares the same timestamp, so the group mean
    uses no information from after that minute. Groups of one are dropped
    (their demeaned target is 0 by construction and carries no ranking
    information)."""
    key = d.astype(np.int64) * 1000 + t.astype(np.int64)
    order = np.argsort(key, kind="stable")
    ks = key[order]
    bnd = np.flatnonzero(np.diff(ks)) + 1
    out = y.copy()
    keep = ok.copy()
    for a, b in zip(np.r_[0, bnd], np.r_[bnd, len(ks)]):
        idx = order[a:b]
        sub = idx[ok[idx]]
        if len(sub) < 3:
            keep[idx] = False
            continue
        out[sub] = y[sub] - y[sub].mean()
    return out, keep


def parse_exit(spec, H):
    if spec.startswith("trail:"):
        p = spec[6:].split(",")
        f = lambda v: None if v in ("", "none", "None") else float(v)
        return ("rule", {"stop": f(p[0]), "take": f(p[1]), "trail": f(p[2]),
                         "tmax": None if f(p[3]) is None else int(float(p[3]))})
    if spec == "flatten":
        return ("flatten",)
    return ("flatten",) if H >= 10 ** 5 else ("horizon", H)


def main():
    import lightgbm as lgb
    a = sys.argv[1:]

    def opt(name, default=None, cast=str):
        return cast(a[a.index(name) + 1]) if name in a else default

    H = opt("--horizon", 30, int)
    rth = bool(opt("--rth", 0, int))
    target = opt("--target", "net")
    q = opt("--q", 0.99, float)
    topk = opt("--topk", 2, int)
    seed = opt("--seed", 0, int)
    variant = opt("--variant", "real")
    exit_spec = opt("--exit", "")
    threads = opt("--threads", None, int)
    tag = opt("--tag", "")
    which = opt("--feat", "feat")
    block = opt("--block", 1, int)
    rounds = opt("--rounds", NROUND, int)
    exit_rule = parse_exit(exit_spec, H) if exit_spec else parse_exit("", H)
    hi = FT.HORIZONS.index(H)

    step_mask = ((FT.STEPS >= FT.RTH_LO) & (FT.STEPS < FT.RTH_HI)) if rth \
        else np.ones(FT.T, bool)
    last_entry = int(np.searchsorted(
        FT.STEPS, RTH_LAST_ENTRY if rth else ANY_LAST_ENTRY, "right") - 1)

    R = DS.Rows(which)
    global FEAT
    FEAT = HERE / "out" / which
    fnames = FT.FEATURE_NAMES
    if which != "feat":
        import features2 as FT2
        fnames = FT2.FEATURE_NAMES2
    y_all = R.Y[:, hi].astype(np.float64)
    ok_all = R.OKY[:, hi].copy()
    if rth:
        ok_all &= step_mask[R.T]
    if target in ("xs", "sign"):
        y_all, ok_all = xs_demean(y_all, R.D, R.T, ok_all)
        if target == "sign":
            y_all = np.sign(y_all)

    # Refit cadence. block=1 is a fresh model every test month (the strict
    # default); block=3 refits quarterly, which is still walk-forward -- the
    # model for a block sees only rows dated before the block starts -- and
    # costs 3x less CPU. This PC is shared with another agent's jobs, so the
    # cadence is a compute decision, stated rather than hidden.
    blocks = [TEST_MONTHS[i:i + block] for i in range(0, len(TEST_MONTHS), block)]
    all_trades, per_month = [], []
    feat_gain = None
    t0 = time.time()
    for grp in blocks:
        m = grp[0]
        lo, hiD = f"{m}-01", month_end(grp[-1])
        tr = (R.date_of_row < lo) & ok_all
        te_dates = [d for d in R.dates if lo <= d < hiD]
        if not te_dates or tr.sum() < 50_000:
            continue
        ytr = y_all[tr]
        if variant == "shuffled":
            rng = np.random.default_rng(seed + 991)
            dd = R.D[tr]
            order = np.argsort(dd, kind="stable")
            ds_ = dd[order]
            bnd = np.flatnonzero(np.diff(ds_)) + 1
            sh = ytr.copy()
            for x, yq in zip(np.r_[0, bnd], np.r_[bnd, len(ds_)]):
                idx = order[x:yq]
                sh[idx] = ytr[rng.permutation(idx)]
            ytr = sh
        p = dict(PARAMS)
        if threads:
            p["num_threads"] = threads
        p.update(seed=seed, bagging_seed=seed + 1, feature_fraction_seed=seed + 2)
        booster = lgb.train(p, lgb.Dataset(R.X[tr], label=ytr),
                            num_boost_round=rounds)
        sub = np.random.default_rng(7).choice(np.flatnonzero(tr),
                                              size=min(200_000, int(tr.sum())),
                                              replace=False)
        thr = float(np.quantile(booster.predict(R.X[sub]), q))
        mt = []
        for dte in te_dates:
            day = SM.Day(FEAT / f"{dte}.npz")
            sc = np.full((FT.T, day.S), -np.inf, np.float64)
            prn = day.printed & step_mask[:, None]
            t_i, s_i = np.nonzero(prn)
            if not len(t_i):
                continue
            sc[t_i, s_i] = booster.predict(day.F[t_i, s_i])
            mt += SM.run_day(day, sc, exit_rule, min_score=thr,
                             max_new_per_step=topk,
                             last_entry_step=last_entry)[0]
        mm = BAR.metrics(mt, te_dates, "+".join(grp))
        mm["threshold"] = round(thr, 6)
        per_month.append(mm)
        all_trades += mt
        imp = booster.feature_importance("gain")
        feat_gain = sorted([[fnames[i], round(float(imp[i]), 1)]
                            for i in range(len(imp))], key=lambda x: -x[1])[:10]
        print(f"  {mm['label']}: {mm['tickets']:4d} tkt  ${mm['total']:>9,.0f}  "
              f"{mm['per_ticket']:+8.2f}/tkt  thr {thr:+.5f}", flush=True)

    dates = [d for d in R.dates
             if f"{TEST_MONTHS[0]}-01" <= d < month_end(TEST_MONTHS[-1])]
    name = (f"bandit2_{variant}_h{H}_{'rth' if rth else 'any'}_{target}"
            f"_q{q}_k{topk}_{exit_spec or 'hz'}_{which}"
            f"_b{block}r{rounds}_s{seed}{tag}")
    mtot = BAR.metrics(all_trades, dates, name)
    rate = mtot["tickets_per_day"]
    p_entry = min(0.9, max(1e-5, rate / (FT.T * 60.0) * 8))
    rc = BAR.random_control([SM.Day(FEAT / f"{d}.npz") for d in dates], dates,
                            exit_rule, p_entry, topk, seeds=30,
                            step_mask=step_mask, T=FT.T)
    out = {"config": {"horizon": H, "rth": rth, "target": target, "q": q,
                      "topk": topk, "seed": seed, "variant": variant,
                      "feat": which, "block": block,
                      "rounds": rounds,
                      "exit": exit_spec or f"horizon:{H}"},
           "overall": mtot, "verdict": BAR.verdict(mtot, rc),
           "random_control": {k: v for k, v in rc.items()
                              if k not in ("total", "total_ex_best")},
           "per_month": per_month, "feature_gain": feat_gain,
           "wall_s": round(time.time() - t0, 1)}
    RES.mkdir(parents=True, exist_ok=True)
    (RES / f"{name}.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({"overall": mtot, "verdict": out["verdict"],
                      "random": out["random_control"]}, indent=1))
    print("wrote", RES / f"{name}.json", flush=True)


if __name__ == "__main__":
    main()
