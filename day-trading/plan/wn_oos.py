"""WIDE-NET (2026-09-16) steps 3 + 4: single-stock out-of-sample validation
of every pattern the train window nominated, with the full control battery.

STEP 3 -- ONE $15,000 TICKET A DAY.  For each pattern, on each OOS day, at
the pattern's own decision time, among the eligible names that match, buy
the single best-matching one and exit at the pattern's horizon (or at the
forced flatten).  No second ticket, no re-entry.

  rule patterns  score = the rule's MARGIN: the mean, over the rule's
                 numeric conditions, of the signed excess past the
                 threshold divided by that feature's TRAIN standard
                 deviation.  Ties inside a set are broken by margin, never
                 by anything computed after the decision minute.
  model pattern  score = the walk-forward LightGBM prediction for that row
                 (plan/wn_model.py --stage wf), whose model for month M was
                 fitted only on rows with date < M.

STEP 4 -- BREADTH.  The same score, top-k with k in {3, 5, 10}, to check
whether spreading the day's capital beats concentrating it.

CONTROLS (every one uses the identical eligibility, fills, costs and exit)
  random-30    30 seeds of a uniform score -> the null single-pick
               distribution; a pattern is reported at its PERCENTILE in it
  inverted     score negated; a real edge must lose when inverted
  shuffled     the model refitted on labels permuted WITHIN each train day
  poison       plan/wn_poison.py -- garbage every bar after the decision
               minute, rebuild features, assert the picks are identical

Usage: python plan/wn_oos.py
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from wn_lib import OUT, Table, single_pick, summarize, write_json  # noqa: E402
from wn_rules import RTH, apply_rule                               # noqa: E402

NRAND = 30


# ------------------------------------------------------------ rule score
def rule_margin(t, rule):
    """Continuous 'how well does this row match' score, built only from
    TRAIN-window standard deviations."""
    tr = t.split == 0
    sc = np.zeros(len(t.date_i))
    k = 0
    for cond in rule:
        if cond.startswith("dec==") or cond.startswith("sic2=="):
            continue
        if "<=" in cond:
            f, v = cond.split("<=")
            sgn = -1.0
        else:
            f, v = cond.split(">")
            sgn = +1.0
        x = t.F[:, t.fidx[f]].astype(np.float64)
        sd = float(np.std(x[tr])) or 1.0
        sc += sgn * (x - float(v)) / sd
        k += 1
    return sc / max(k, 1)


def eval_pattern(t, mask, score, h, label, split=1, topk=1, rng=None):
    p, d, idx = single_pick(t, score, mask & np.isin(t.split, split), h,
                            topk=topk, rng=rng)
    nd = t.ndays(split if np.isscalar(split) else split[0])
    s = summarize(p, d, nd, label)
    s["topk"] = topk
    s["h"] = h
    return s, idx


def random_null(t, mask, h, split=1, topk=1, n=NRAND):
    vals = []
    for s in range(n):
        rng = np.random.default_rng(10_000 + s)
        sc = rng.random(len(t.date_i))
        r, _ = eval_pattern(t, mask, sc, h, f"random_s{s}", split, topk, rng)
        vals.append(r)
    pt = np.array([v["per_ticket"] for v in vals])
    pm = np.array([v["per_month"] for v in vals])
    return {"n_seeds": n, "per_ticket_mean": round(float(pt.mean()), 2),
            "per_ticket_sd": round(float(pt.std(ddof=1)), 2),
            "per_ticket_min": round(float(pt.min()), 2),
            "per_ticket_max": round(float(pt.max()), 2),
            "per_month_mean": round(float(pm.mean()), 2),
            "_vals": pt.tolist()}


def pctile(v, arr):
    a = np.asarray(arr)
    return round(float((a < v).mean() * 100), 1)


# ------------------------------------------------------------------ main
def main():
    t = Table()
    rules = json.loads((OUT / "rules_search.json").read_text())
    rules.sort(key=lambda r: -r["train_mean"])
    report = {"rules": [], "model": [], "breadth": [], "nulls": {}}

    # ---- de-duplicate: one entry per distinct rule, best train first
    seen, pats = set(), []
    for r in rules:
        k = (r["h"], tuple(sorted(r["rule"])))
        if k in seen:
            continue
        seen.add(k)
        pats.append(r)
    pats = pats[:8]

    print("=== STEP 3: single $15,000 ticket a day, OOS 2025-08-01 .. "
          "2026-07-31 ===\n")
    hdr = (f"{'pattern':>34} {'h':>5} {'tkt':>5} {'$/tkt':>8} {'total':>10} "
           f"{'$/mo':>8} {'mo+':>6} {'maxDD':>9} {'pct':>5}")
    print(hdr)
    for r in pats:
        h = r["h"]
        m = apply_rule(t, r["rule"], h)
        sc = rule_margin(t, r["rule"])
        sc = np.where(m, sc, -np.inf)
        res, idx = eval_pattern(t, m, sc, h, " AND ".join(r["rule"]), 1)
        inv, _ = eval_pattern(t, m, np.where(m, -sc, -np.inf), h, "inverted", 1)
        key = f"{h}|{'&'.join(sorted(r['rule']))}"
        if key not in report["nulls"]:
            report["nulls"][key] = random_null(t, m, h, 1)
        nul = report["nulls"][key]
        res["percentile_vs_random"] = pctile(res["per_ticket"], nul["_vals"])
        res["random_mean"] = nul["per_ticket_mean"]
        res["random_sd"] = nul["per_ticket_sd"]
        res["inverted_per_ticket"] = inv["per_ticket"]
        res["train_mean"] = r["train_mean"]
        res["train_n"] = r["train_n"]
        res["rule"] = r["rule"]
        res["seed"] = r["seed"]
        # aug2026 stub
        a, _ = eval_pattern(t, m, sc, h, "aug2026", 2)
        res["aug2026"] = {"tickets": a["tickets"], "total": a["total"],
                          "per_ticket": a["per_ticket"]}
        report["rules"].append(res)
        nm = " AND ".join(r["rule"])
        print(f"{nm[:34]:>34} {h:>5} {res['tickets']:>5} "
              f"{res['per_ticket']:>8.2f} {res['total']:>10,.0f} "
              f"{res['per_month']:>8.0f} {res['months_pos']:>6} "
              f"{res['max_dd']:>9,.0f} {res['percentile_vs_random']:>5.1f}")

    # ---- model pattern, walk-forward -----------------------------------
    print("\n=== STEP 3b: walk-forward LightGBM, single ticket a day ===")
    for f in sorted(OUT.glob("model_scores_*.npy")):
        sc = np.load(f).astype(np.float64)
        h = f.stem.split("_")[2]
        m = t.mask(split=None, dec=RTH, h=h) & np.isfinite(sc)
        s2 = np.where(m, sc, -np.inf)
        res, _ = eval_pattern(t, m, s2, h, f.stem, 1)
        inv, _ = eval_pattern(t, m, np.where(m, -sc, -np.inf), h, "inv", 1)
        key = f"model|{h}"
        if key not in report["nulls"]:
            report["nulls"][key] = random_null(t, m, h, 1)
        nul = report["nulls"][key]
        res["percentile_vs_random"] = pctile(res["per_ticket"], nul["_vals"])
        res["random_mean"] = nul["per_ticket_mean"]
        res["inverted_per_ticket"] = inv["per_ticket"]
        a, _ = eval_pattern(t, m, s2, h, "aug2026", 2)
        res["aug2026"] = {"tickets": a["tickets"], "total": a["total"],
                          "per_ticket": a["per_ticket"]}
        report["model"].append(res)
        print(f"{f.stem[:34]:>34} {h:>5} {res['tickets']:>5} "
              f"{res['per_ticket']:>8.2f} {res['total']:>10,.0f} "
              f"{res['per_month']:>8.0f} {res['months_pos']:>6} "
              f"{res['max_dd']:>9,.0f} {res['percentile_vs_random']:>5.1f}")
        # ---- STEP 4: breadth on the model score
        if "shuf" not in f.stem:
            for k in (3, 5, 10):
                b, _ = eval_pattern(t, m, s2, h, f"{f.stem}_top{k}", 1, topk=k)
                nb = random_null(t, m, h, 1, topk=k, n=10)
                b["percentile_vs_random"] = pctile(b["per_ticket"], nb["_vals"])
                b["random_mean"] = nb["per_ticket_mean"]
                report["breadth"].append(b)

    # ---- STEP 4 on the best rule ---------------------------------------
    if report["rules"]:
        best = max(report["rules"], key=lambda r: r["per_month"])
        m = apply_rule(t, best["rule"], best["h"])
        sc = np.where(m, rule_margin(t, best["rule"]), -np.inf)
        for k in (3, 5, 10):
            b, _ = eval_pattern(t, m, sc, best["h"], f"bestrule_top{k}", 1,
                                topk=k)
            nb = random_null(t, m, best["h"], 1, topk=k, n=10)
            b["percentile_vs_random"] = pctile(b["per_ticket"], nb["_vals"])
            b["random_mean"] = nb["per_ticket_mean"]
            b["rule"] = best["rule"]
            report["breadth"].append(b)

    print("\n=== STEP 4: breadth (top-k a day) ===")
    print(f"{'label':>34} {'k':>3} {'tkt':>6} {'$/tkt':>8} {'$/mo':>9} "
          f"{'mo+':>6} {'rand $/tkt':>11} {'pct':>5}")
    for b in report["breadth"]:
        print(f"{b['label'][:34]:>34} {b['topk']:>3} {b['tickets']:>6} "
              f"{b['per_ticket']:>8.2f} {b['per_month']:>9.0f} "
              f"{b['months_pos']:>6} {b['random_mean']:>11.2f} "
              f"{b['percentile_vs_random']:>5.1f}")

    for v in report["nulls"].values():
        v.pop("_vals", None)
    write_json("oos_report.json", report)
    print("\nwritten data/massive/wn/oos_report.json")


if __name__ == "__main__":
    main()
