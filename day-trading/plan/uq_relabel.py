"""UNIVERSE+QUOTES (2026-09-16) -- constraint 2, stage 6: refit the SAME
model on the LIMIT label and see whether the edge comes back.

plan/uq_label.py explains why: the wide-net ranker was fitted on the P&L
of a ticket that always fills at the next bar's open, and a limit only
fills when the price comes down to it, so the ranking is applied to a
conditional population it never saw. Here the label is the limit ticket's
own realized P&L ($0 when it did not fill) and NOTHING ELSE CHANGES --
same 32 causal features, same `wn_model.fit` (imported), same LightGBM
params, same early stopping on the last 10% of train days, same monthly
walk-forward so no test month informs its own model.

Two walk-forwards are produced:
  train  months 2025-01..2025-07, each fitted on train rows before it --
         used ONLY to choose the limit configuration
  oos    months 2025-08..2026-07, each fitted on every row before it --
         read once, and only after the configuration is fixed

Usage:
  python plan/uq_relabel.py --stage scores [--offset 10] [--wait 1]
  python plan/uq_relabel.py --stage eval   [--offset 10] [--wait 1]
                            [--split 1] [--seeds 30]
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import uq_econ as UE                                          # noqa: E402
import uq_fills as UF                                         # noqa: E402
import uq_label as UL                                         # noqa: E402
import uq_strat as US                                         # noqa: E402
from wn_lib import Table                                      # noqa: E402

OUT = HERE / "uq_out"
RTH = UF.RTH_DEC


def score_path(h, offset, wait, exit_bps, split):
    return OUT / (f"relabel_scores_{h}_o{offset:.0f}_w{wait}"
                  f"_x{exit_bps:.0f}_s{split}.npy")


def stage_scores(h="h30", offset=10.0, wait=1, exit_bps=UF.FEE_BPS, seed=0):
    import wn_model
    z = np.load(UL.path(h, offset, wait, exit_bps))
    t = Table()
    t.pnl["lim"] = z["y"].astype(np.float32)
    have = z["have"]
    m = t.mask(split=None, dec=RTH, h=h) & have
    rows = np.flatnonzero(m)
    print(f"relabel: {len(rows):,} labelled eligible rows", flush=True)
    for split, months in ((0, [f"2025-0{i}" for i in range(1, 8)]),
                          (1, sorted({x for x in t.month[rows]
                                      if x >= "2025-08"}))):
        score = np.full(len(t.date_i), np.nan)
        pool = rows[t.split[rows] == 0] if split == 0 else rows
        for mo in months:
            te = pool[t.month[pool] == mo]
            tr = pool[t.month[pool] < mo]
            if len(tr) < 5000 or len(te) == 0:
                continue
            dd = t.date_i[tr]
            cut = np.quantile(np.unique(dd), 0.9)
            bst = wn_model.fit(t, tr[dd < cut], "lim", seed,
                               valid_rows=tr[dd >= cut])
            score[te] = bst.predict(t.F[te])
            print(f"  [{split}] {mo} train={len(tr):,} test={len(te):,} "
                  f"iters={bst.best_iteration}", flush=True)
        np.save(score_path(h, offset, wait, exit_bps, split),
                score.astype(np.float32))
        print(f"  -> {score_path(h, offset, wait, exit_bps, split).name}: "
              f"{int(np.isfinite(score).sum()):,} scored rows", flush=True)


def stage_eval(h="h30", offset=10.0, wait=1, exit_bps=UF.FEE_BPS, split=1,
               seeds=30, post_k=1, max_tickets=7):
    t = Table()
    sc = np.load(score_path(h, offset, wait, exit_bps, split)).astype(float)
    days = [d for d in UE.cached_days(t, split)
            if np.isfinite(sc[t.date_i == t.dates.index(d)]).any()]
    nd = len(days)
    fin = np.isfinite(sc)
    scores = [sc, -sc]
    for s in range(seeds):
        rg = np.random.default_rng(2000 + s)
        scores.append(np.where(fin, rg.random(len(sc)), np.nan))
    kw = dict(offset=offset, wait=wait, post_k=post_k, h=h,
              exit_bps=exit_bps, passive_bps=0.0, max_tickets=max_tickets)
    configs = [dict(kw), dict(kw, market=True)]
    print(f"relabel eval: {nd} days, split {split}, offset {offset}, "
          f"wait {wait}, post_k {post_k}", flush=True)
    acc = US.run_many(t, days, scores, configs)
    rep = {"h": h, "offset_bps": offset, "wait_min": wait, "split": split,
           "post_k": post_k, "days": nd, "exit_bps": exit_bps,
           "label": "limit-fill P&L"}
    rep["model_limit"] = US._summ(acc[(0, 0)], nd, "relabelled, limit")
    rep["model_market"] = US._summ(acc[(1, 0)], nd, "relabelled, market")
    rep["inverted"] = US._summ(acc[(0, 1)], nd, "inverted, limit")
    rnd = [US._summ(acc[(0, 2 + s)], nd, "") for s in range(seeds)]
    pt = np.array([x["per_ticket"] for x in rnd])
    pm = np.array([x["per_month"] for x in rnd])
    rep["random"] = {"seeds": seeds,
                     "per_ticket_mean": round(float(pt.mean()), 2),
                     "per_ticket_sd": round(float(pt.std(ddof=1)), 2),
                     "per_month_mean": round(float(pm.mean()), 1),
                     "per_month_sd": round(float(pm.std(ddof=1)), 1)}
    rep["percentile_vs_random_per_month"] = round(
        100.0 * float(np.mean(pm < rep["model_limit"]["per_month"])), 1)
    rep["percentile_vs_random_per_ticket"] = round(
        100.0 * float(np.mean(pt < rep["model_limit"]["per_ticket"])), 1)
    rep["edge_vs_random_per_ticket"] = round(
        rep["model_limit"]["per_ticket"] - float(pt.mean()), 2)
    nm = (f"relabel_eval_{h}_o{offset:.0f}_w{wait}_k{post_k}_s{split}.json")
    (OUT / nm).write_text(json.dumps(rep, indent=1, default=str))
    for k in ("model_limit", "model_market", "inverted"):
        v = rep[k]
        print(f"{k:>14}: {v['tickets']:>5} tkts ({v['tickets_per_day']:.2f}"
              f"/day) ${v['per_ticket']:>8.2f}/tkt ${v['per_month']:>9.0f}/mo"
              f"  mo+ {v['months_pos']}")
    print("random:", json.dumps(rep["random"]))
    print(f"edge vs random ${rep['edge_vs_random_per_ticket']:+.2f}/tkt; "
          f"percentile {rep['percentile_vs_random_per_month']}")
    return rep


if __name__ == "__main__":
    a = sys.argv
    g = lambda f, d: (type(d)(a[a.index(f) + 1]) if f in a else d)  # noqa: E731
    st = g("--stage", "scores")
    if st == "scores":
        stage_scores(g("--h", "h30"), g("--offset", 10.0), g("--wait", 1),
                     g("--exit", UF.FEE_BPS))
    else:
        stage_eval(g("--h", "h30"), g("--offset", 10.0), g("--wait", 1),
                   g("--exit", UF.FEE_BPS), g("--split", 1),
                   g("--seeds", 30), g("--postk", 1))
