"""OPEN-UNIVERSE (2026-09-17) TEST 2, step 3: the walk-forward ranker.

WIDE-NET's walk-forward LightGBM found real skill (+$24/ticket over a matched
random control, 97th percentile) on 61 halal names a day and still lost money
net; COST-REBASE then showed that most of the LEVEL was the flat toll
under-charging the names the ranker liked.  The open universe changes both
sides of that: 600 names a day instead of 61, and books deep enough that the
measured toll is a fraction of the flat one.  This module re-runs the same
procedure there.

PROCEDURE, unchanged from plan/wn_model.py
  * refit once per test MONTH on every row with date < that month, so no test
    month ever informs its own model;
  * label = the realized NET dollar P&L of the $15,000 ticket, not a return,
    so the model optimises the thing the mandate scores;
  * early stopping on the last 10% of TRAIN days.

CONTROLS
  * CORRECTED SHUFFLE -- labels permuted WITHIN each train day, so per-day
    sums are preserved and only the row-to-outcome link is destroyed.  A
    model trained on this must land on the random control.
  * INVERTED -- the fitted score with its sign flipped.
  * 30-seed RANDOM ordering over the identical candidate set.
  * FORESIGHT -- the label itself as the score, the positive control: it must
    come out hugely positive or the pipeline is not wired to the money.

Usage:
  python plan/ou_model.py --stage wf   [--h h30] [--seed 0] [--shuffle]
  python plan/ou_model.py --stage oos  [--h h30]
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ou_lib as L                                            # noqa: E402
import ou_cost as OC                                          # noqa: E402
import ou_rank as OR                                          # noqa: E402

RTH = OR.RTH_DEC
PARAMS = dict(objective="regression", learning_rate=0.04, num_leaves=63,
              min_data_in_leaf=400, feature_fraction=0.8,
              bagging_fraction=0.8, bagging_freq=1, lambda_l2=5.0,
              verbose=-1, num_threads=8)
NROUND = 600
SEEDS = 30


def _cat_idx(t):
    return [t.fidx["sic2"], t.fidx["dow"]]


def fit(t, rows, h, seed, nround=NROUND, valid_rows=None):
    import lightgbm as lgb
    p = dict(PARAMS, seed=seed, bagging_seed=seed, feature_fraction_seed=seed)
    ds = lgb.Dataset(t.F[rows], label=t.pnl[h][rows], feature_name=t.feat,
                     categorical_feature=_cat_idx(t), free_raw_data=False)
    if valid_rows is not None and len(valid_rows):
        va = lgb.Dataset(t.F[valid_rows], label=t.pnl[h][valid_rows],
                         reference=ds)
        return lgb.train(p, ds, nround, valid_sets=[va],
                         callbacks=[lgb.early_stopping(50, verbose=False)])
    return lgb.train(p, ds, nround)


def stage_wf(h="h30", seed=0, shuffle=False, tag=""):
    t = OR.OT()
    m = t.mask(split=None, dec=RTH, h=h)
    rows = np.flatnonzero(m)
    months = sorted({x for x in t.month[rows] if x >= "2025-08"})
    score = np.full(len(t.date_i), np.nan)
    rng = np.random.default_rng(seed)
    info = []
    for mo in months:
        te = rows[t.month[rows] == mo]
        tr = rows[t.month[rows] < mo]
        if len(tr) < 5000 or len(te) == 0:
            continue
        if shuffle:
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
                     "iters": int(bst.best_iteration or NROUND)})
        print(f"  {mo} train={len(tr):,} test={len(te):,} "
              f"iters={bst.best_iteration or NROUND}", flush=True)
    nm = f"model_scores_{h}_s{seed}{'_shuf' if shuffle else ''}{tag}.npy"
    np.save(L.OUT / nm, score.astype(np.float32))
    L.write(nm.replace(".npy", "_folds.json"), info)
    print(json.dumps({"file": nm, "months": len(info),
                      "scored_rows": int(np.isfinite(score).sum())}),
          flush=True)


def _pol(t, score, h, dec, k, cm, label, split=1):
    m = t.mask(split=split, dec=dec, h=h) & np.isfinite(score)
    pk = OR.picks(t, score, m, k)
    if pk.size == 0:
        return None, None
    a = OR.score_stats(t, t.pnl[h][pk], pk, label)
    a["cost_model"] = "flat10"
    a["ic"] = round(float(OR.ic_of(t, score, m, h)), 4)
    b = OR.score_stats(t, t.measured_pnl(h, pk, cm), pk, label)
    b["cost_model"] = "measured"
    b["ic"] = a["ic"]
    return a, b


def stage_oos(h="h30", seeds=(0, 1, 2)):
    t = OR.OT()
    cm = OC.MinuteCost()
    out = {"h": h, "rows": [], "controls": {}}
    for sd in seeds:
        f = L.OUT / f"model_scores_{h}_s{sd}.npy"
        if not f.exists():
            continue
        sc = np.load(f).astype(np.float64)
        for dec in ("09:35", "10:00", "10:30", "11:00", "13:00"):
            for k in (1, 3, 5, 7):
                a, b = _pol(t, sc, h, dec, k, cm, f"MODEL s{sd}|{dec}|k{k}")
                if a:
                    out["rows"] += [a, b]
        a, b = _pol(t, -sc, h, "10:00", 7, cm, f"INVERTED s{sd}|10:00|k7")
        if a:
            out["rows"] += [a, b]
        fs = L.OUT / f"model_scores_{h}_s{sd}_shuf.npy"
        if fs.exists():
            ss = np.load(fs).astype(np.float64)
            a, b = _pol(t, ss, h, "10:00", 7, cm, f"SHUFFLED s{sd}|10:00|k7")
            if a:
                out["rows"] += [a, b]
    # foresight positive control + 30-seed random control, same candidate set
    fore = t.pnl[h].astype(np.float64)
    a, _ = _pol(t, fore, h, "10:00", 7, cm, "FORESIGHT|10:00|k7")
    if a:
        out["rows"].append(a)
    rnd = []
    for s in range(SEEDS):
        rng = np.random.default_rng(2100 + s)
        m = t.mask(split=1, dec="10:00", h=h)
        pk = OR.picks(t, rng.random(len(t.pnl[h])), m, 7)
        rnd.append(OR.score_stats(t, t.pnl[h][pk], pk, f"rand{s}"))
    rm = np.array([r["per_month"] for r in rnd])
    rt = np.array([r["per_ticket"] for r in rnd])
    out["controls"]["random_k7_10:00"] = {
        "per_month_mean": round(float(rm.mean()), 2),
        "per_month_sd": round(float(rm.std(ddof=1)), 2),
        "per_ticket_mean": round(float(rt.mean()), 2),
        "seeds": SEEDS}
    for r in out["rows"]:
        if r["cost_model"] == "flat10":
            r["pct_vs_random"] = L.percentile_of(r["per_month"], rm)
            r["edge_per_ticket"] = round(r["per_ticket"] - float(rt.mean()), 2)
    out["rows"].sort(key=lambda r: -r["per_month"])
    out["cost_report"] = cm.report()
    L.write(f"model_oos_{h}.json", out)
    for r in out["rows"][:18]:
        print(f"[oos] {r['label']:30s} {r['cost_model']:8s} "
              f"${r['per_month']:+9,.0f}/mo ${r['per_ticket']:+8.2f}/tkt "
              f"n={r['tickets']:5d} Y2 {r['y2_per_month']} "
              f"pct {r.get('pct_vs_random')}", flush=True)
    print(f"[oos] random k7 10:00: "
          f"${out['controls']['random_k7_10:00']['per_month_mean']:+,.0f}/mo "
          f"${out['controls']['random_k7_10:00']['per_ticket_mean']:+.2f}/tkt",
          flush=True)


def main():
    a = sys.argv
    st = a[a.index("--stage") + 1] if "--stage" in a else "wf"
    h = a[a.index("--h") + 1] if "--h" in a else "h30"
    sd = int(a[a.index("--seed") + 1]) if "--seed" in a else 0
    if st == "wf":
        stage_wf(h, sd, shuffle="--shuffle" in a)
    else:
        stage_oos(h)


if __name__ == "__main__":
    main()
