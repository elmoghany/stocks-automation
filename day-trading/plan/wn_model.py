"""WIDE-NET (2026-09-16) step 2b: the gradient-boosted ranker and its
TreeSHAP attribution, plus step 3's model variant (walk-forward monthly).

TRAIN-ONLY ATTRIBUTION.  `--stage shap` fits one LightGBM regressor on the
train window (2024-10-22 .. 2025-07-31), holds out the last 20% of train
DAYS for early stopping, and ranks features by mean |TreeSHAP| computed
with LightGBM's own `pred_contrib=True` (exact Shapley values for trees --
the `shap` package is not installed and is not needed).  Pairwise
interactions are ranked by the gain of the 2-feature splits LightGBM
actually chose.

WALK-FORWARD.  `--stage wf` refits once per test month M on every row with
date < M and scores month M, so no test month ever informs its own model.
The per-month scores are written to data/massive/wn/model_scores_*.npy and
consumed by plan/wn_oos.py, which is the only place a dollar is counted.

Labels are the realized NET dollar P&L of the $15,000 ticket (the same
number plan/rl2/sim.py would book), never a raw return, so the model
optimizes the thing the mandate is scored on.

Usage: python plan/wn_model.py --stage shap
       python plan/wn_model.py --stage wf [--h h30] [--seed 0]
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from wn_lib import OUT, Table, write_json          # noqa: E402

RTH = ["09:35", "09:45", "10:00", "10:30", "11:00", "12:00", "13:00",
       "14:00", "15:00"]
PARAMS = dict(objective="regression", learning_rate=0.04, num_leaves=63,
              min_data_in_leaf=400, feature_fraction=0.8,
              bagging_fraction=0.8, bagging_freq=1, lambda_l2=5.0,
              verbose=-1, num_threads=8)
NROUND = 600


def _cat_idx(t):
    return [t.fidx["sic2"], t.fidx["dow"]]


def fit(t, rows, h, seed, nround=NROUND, valid_rows=None):
    import lightgbm as lgb
    p = dict(PARAMS, seed=seed, bagging_seed=seed, feature_fraction_seed=seed)
    ds = lgb.Dataset(t.F[rows], label=t.pnl[h][rows],
                     feature_name=t.feat, categorical_feature=_cat_idx(t),
                     free_raw_data=False)
    if valid_rows is not None and len(valid_rows):
        va = lgb.Dataset(t.F[valid_rows], label=t.pnl[h][valid_rows],
                         reference=ds)
        return lgb.train(p, ds, nround, valid_sets=[va],
                         callbacks=[lgb.early_stopping(50, verbose=False)])
    return lgb.train(p, ds, nround)


# ------------------------------------------------------------------ shap
def stage_shap(h="h30", seed=0):
    t = Table()
    m = t.mask(split=0, dec=RTH, h=h)
    rows = np.flatnonzero(m)
    d = t.date_i[rows]
    cut = np.quantile(np.unique(d), 0.8)
    tr, va = rows[d < cut], rows[d >= cut]
    print(f"train rows {len(tr):,}  early-stop rows {len(va):,}", flush=True)

    # (1) GENERALIZATION DIAGNOSTIC -- how many boosting rounds actually
    # help on held-out TRAIN days.  This number is the headline, not the
    # attribution: 1 means the label is noise at this feature resolution.
    es = fit(t, tr, h, seed, valid_rows=va)
    nes = int(es.best_iteration or 0)
    l2 = float(es.best_score["valid_0"]["l2"]) if es.best_score else float("nan")
    base = float(np.mean((t.pnl[h][va] - t.pnl[h][tr].mean()) ** 2))
    print(f"EARLY STOPPING chose {nes} rounds; held-out-train-day MSE "
          f"{l2:,.0f} vs constant-mean {base:,.0f} "
          f"(R2 = {1 - l2 / base:+.5f})", flush=True)

    # (2) ATTRIBUTION -- a fixed-round fit on the whole train window.  It
    # is deliberately over-fitted; its only job is to say WHICH features
    # the trees reach for, which is a description of the train sample.
    # TreeSHAP costs O(trees x leaves x depth^2) per row, so the
    # attribution model is deliberately small (150 x 31); the ranking it
    # produces is stable across sizes and it is a description, not a
    # forecast.
    import lightgbm as lgb
    pa = dict(PARAMS, seed=seed, num_leaves=31, learning_rate=0.06)
    ds = lgb.Dataset(t.F[rows], label=t.pnl[h][rows], feature_name=t.feat,
                     categorical_feature=_cat_idx(t), free_raw_data=False)
    bst = lgb.train(pa, ds, 150)
    sub = rows[np.random.default_rng(seed).choice(
        len(rows), min(6000, len(rows)), replace=False)]
    contrib = bst.predict(t.F[sub], pred_contrib=True)      # [n, NF+1]
    mad = np.abs(contrib[:, :-1]).mean(axis=0)
    gain = bst.feature_importance("gain")
    order = np.argsort(-mad)
    res = [{"feature": t.feat[i], "mean_abs_shap": round(float(mad[i]), 3),
            "gain": round(float(gain[i]), 1),
            "shap_corr_with_value": round(float(np.corrcoef(
                t.F[sub][:, i], contrib[:, i])[0, 1]), 3)
            if np.std(t.F[sub][:, i]) > 0 else 0.0} for i in order]
    print(f"\n=== TreeSHAP on train ({h}) ===")
    print(f"{'feature':>18} {'|shap| $':>9} {'gain':>12} {'dir':>6}")
    for r in res:
        print(f"{r['feature']:>18} {r['mean_abs_shap']:>9.2f} "
              f"{r['gain']:>12.1f} {r['shap_corr_with_value']:>6.2f}")

    # interactions: top split pairs by combined gain along root->leaf paths
    dmp = bst.dump_model()
    pair = {}
    for tree in dmp["tree_info"]:
        def walk(node, anc):
            if "split_index" not in node:
                return
            f = node["split_feature"]
            g = node["split_gain"]
            for a in anc:
                if a != f:
                    k = tuple(sorted((a, f)))
                    pair[k] = pair.get(k, 0.0) + g
            walk(node["left_child"], anc + [f])
            walk(node["right_child"], anc + [f])
        walk(tree["tree_structure"], [])
    tops = sorted(pair.items(), key=lambda kv: -kv[1])[:15]
    inter = [{"a": t.feat[a], "b": t.feat[b], "gain": round(g, 1)}
             for (a, b), g in tops]
    print("\n=== top feature INTERACTIONS by co-split gain ===")
    for r in inter:
        print(f"  {r['a']:>18} x {r['b']:<18} {r['gain']:>12.1f}")
    write_json(f"model_shap_{h}.json",
               {"h": h, "seed": seed, "best_iteration": bst.best_iteration,
                "shap": res, "interactions": inter})

    # what the model's own top decile looks like ON TRAIN (in-sample --
    # reported only to show the model CAN fit, never as evidence of edge)
    pr = bst.predict(t.F[rows])
    q = np.quantile(pr, np.linspace(0, 1, 11))
    b = np.clip(np.searchsorted(q, pr, "right") - 1, 0, 9)
    p = t.pnl[h][rows]
    print("\n=== in-sample decile of model score (NOT evidence) ===")
    for i in range(10):
        k = b == i
        print(f"  d{i} n={k.sum():>6} ${p[k].mean():+8.2f}/tkt "
              f"win={float((p[k]>0).mean()):.3f}")


# -------------------------------------------------------- walk-forward
def stage_wf(h="h30", seed=0, shuffle=False, tag=""):
    t = Table()
    m = t.mask(split=None, dec=RTH, h=h)
    rows = np.flatnonzero(m)
    months = sorted({x for x in t.month[rows] if x >= "2025-08"})
    score = np.full(len(t.date_i), np.nan)
    rng = np.random.default_rng(seed)
    info = []
    for mi, mo in enumerate(months):
        te = rows[t.month[rows] == mo]
        tr = rows[t.month[rows] < mo]
        if len(tr) < 5000 or len(te) == 0:
            continue
        if shuffle:
            # CORRECTED SHUFFLE: permute labels WITHIN each train day, so
            # per-day sums are preserved but a row's features no longer
            # know its own outcome.
            lab = t.pnl[h][tr].copy()
            d = t.date_i[tr]
            o = np.argsort(d, kind="stable")
            ds = d[o]
            st = np.flatnonzero(np.r_[True, ds[1:] != ds[:-1]])
            en = np.r_[st[1:], len(o)]
            for a, b in zip(st, en):
                lab[o[a:b]] = lab[o[a:b]][rng.permutation(b - a)]
            saved = t.pnl[h].copy()
            t.pnl[h][tr] = lab
            bst = fit(t, tr, h, seed, nround=300)
            t.pnl[h] = saved
        else:
            dd = t.date_i[tr]
            cut = np.quantile(np.unique(dd), 0.9)
            bst = fit(t, tr[dd < cut], h, seed, valid_rows=tr[dd >= cut])
        score[te] = bst.predict(t.F[te])
        info.append({"month": mo, "train_rows": int(len(tr)),
                     "test_rows": int(len(te)),
                     "iters": int(bst.best_iteration or (300 if shuffle else NROUND))})
        print(f"  {mo} train={len(tr):,} test={len(te):,} "
              f"iters={bst.best_iteration or NROUND}", flush=True)
    nm = f"model_scores_{h}_s{seed}{'_shuf' if shuffle else ''}{tag}.npy"
    np.save(OUT / nm, score.astype(np.float32))
    write_json(nm.replace(".npy", "_folds.json"), info)
    print(json.dumps({"file": nm, "months": len(info),
                      "scored_rows": int(np.isfinite(score).sum())}))


if __name__ == "__main__":
    a = sys.argv
    st = a[a.index("--stage") + 1] if "--stage" in a else "shap"
    h = a[a.index("--h") + 1] if "--h" in a else "h30"
    sd = int(a[a.index("--seed") + 1]) if "--seed" in a else 0
    if st == "shap":
        stage_shap(h, sd)
    else:
        stage_wf(h, sd, shuffle="--shuffle" in a)
