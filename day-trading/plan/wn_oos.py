"""WIDE-NET (2026-09-16) steps 3 + 4: single-stock out-of-sample validation
of every pattern the train window nominated, with the full control battery.

STEP 3 -- ONE $15,000 TICKET A DAY.  For each pattern, on each OOS day, at
the EARLIEST decision time on which the pattern fires, buy the single
best-matching eligible name and exit at the pattern's horizon (or at the
forced flatten).  No second ticket, no re-entry, at most one ticket a day.

  Taking the earliest firing time is the only causal way to collapse a
  time-unconstrained rule to one ticket: at 09:35 you cannot know that
  13:00 will score higher.  A rule that names its own decision time
  (`dec==HH:MM`) reduces to that time automatically.

  rule patterns  score = the rule's MARGIN: the mean, over the rule's
                 numeric conditions, of the signed excess past the
                 threshold divided by that feature's TRAIN standard
                 deviation.
  model pattern  score = the walk-forward LightGBM prediction, whose model
                 for month M saw only rows with date < M.

STEP 4 -- BREADTH.  The same score, top-k a day with k in {3, 5, 10}, to
check whether spreading the day's capital beats concentrating it.

CONTROLS (identical eligibility, fills, costs, exit and TIMING)
  random-30    30 seeds that pick a UNIFORMLY RANDOM eligible name in the
               exact (date, decision-time) slots the pattern traded.  This
               is the null that matters: it holds when and how often you
               trade fixed and asks only whether the pattern picked a
               better NAME than a coin flip out of the same ~50 names.
  random-any   30 seeds that also randomise which slots are traded, at the
               pattern's own ticket rate.
  inverted     score negated inside the pattern's own set.
  shuffled     the model refitted on labels permuted WITHIN each train day.
  poison       plan/wn_poison.py.

Usage: python plan/wn_oos.py
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from wn_lib import OUT, Table, summarize, write_json          # noqa: E402
from wn_rules import RTH, apply_rule                          # noqa: E402

NRAND = 30
NRAND_K = 12


# ------------------------------------------------------------ rule score
def rule_margin(t, rule):
    tr = t.split == 0
    sc = np.zeros(len(t.date_i))
    k = 0
    for cond in rule:
        if cond.startswith("dec==") or cond.startswith("sic2=="):
            continue
        if "<=" in cond:
            f, v = cond.split("<="); sgn = -1.0
        else:
            f, v = cond.split(">"); sgn = +1.0
        x = t.F[:, t.fidx[f]].astype(np.float64)
        sd = float(np.std(x[tr])) or 1.0
        sc += sgn * (x - float(v)) / sd
        k += 1
    return sc / max(k, 1)


# ------------------------------------------------------------- selection
def pick(t, mask, score, topk=1, per="day", slots=None):
    """Rows bought.  `per='day'` = at most topk tickets a day, taken at the
    EARLIEST decision time the mask fires (causal).  `per='slot'` = topk at
    every (date, decision-time).  `slots` restricts to a given set of
    (date_i, dec_i) pairs -- used to hold a control's timing fixed."""
    idx = np.flatnonzero(mask & np.isfinite(score))
    if idx.size == 0:
        return np.zeros(0, int)
    if slots is not None:
        key = t.date_i[idx].astype(np.int64) * 64 + t.dec_i[idx]
        idx = idx[np.isin(key, slots)]
        if idx.size == 0:
            return np.zeros(0, int)
    if per == "day":
        # earliest firing decision time per date
        best = {}
        for i, (d, c) in enumerate(zip(t.date_i[idx], t.dec_i[idx])):
            if d not in best or c < best[d]:
                best[d] = c
        keep = np.array([best[d] == c for d, c in
                         zip(t.date_i[idx], t.dec_i[idx])])
        idx = idx[keep]
        grp = t.date_i[idx].astype(np.int64)
    else:
        grp = t.date_i[idx].astype(np.int64) * 64 + t.dec_i[idx]
    order = np.lexsort((-score[idx], grp))
    idx, grp = idx[order], grp[order]
    st = np.flatnonzero(np.r_[True, grp[1:] != grp[:-1]])
    en = np.r_[st[1:], len(idx)]
    return np.concatenate([idx[s:min(s + topk, e)] for s, e in zip(st, en)])


def score_rows(t, rows, h, split, label):
    s = summarize(t.pnl[h][rows], t.date_s[rows], t.ndays(split), label)
    s["h"] = h
    return s


def slots_of(t, rows):
    return np.unique(t.date_i[rows].astype(np.int64) * 64 + t.dec_i[rows])


def random_null(t, elig, h, split, rows_ref, topk=1, n=NRAND, fix_slots=True):
    """Uniform-random name in the same slots (fix_slots) or in randomly
    chosen slots at the same rate."""
    sl = slots_of(t, rows_ref) if fix_slots else None
    per = "slot" if fix_slots else "day"
    vals, tot = [], []
    for s in range(n):
        rng = np.random.default_rng(10_000 + s)
        sc = rng.random(len(t.date_i))
        r = pick(t, elig, sc, topk=topk, per=per, slots=sl)
        if not fix_slots and len(rows_ref):
            keep = rng.choice(len(r), min(len(rows_ref), len(r)),
                              replace=False)
            r = r[np.sort(keep)]
        if r.size == 0:
            continue
        vals.append(float(t.pnl[h][r].mean()))
        tot.append(float(t.pnl[h][r].sum()))
    v = np.array(vals)
    return {"n_seeds": len(v), "per_ticket_mean": round(float(v.mean()), 2),
            "per_ticket_sd": round(float(v.std(ddof=1)), 2),
            "per_ticket_min": round(float(v.min()), 2),
            "per_ticket_max": round(float(v.max()), 2),
            "total_mean": round(float(np.mean(tot)), 0), "_vals": vals}


def pctile(v, arr):
    return round(float((np.asarray(arr) < v).mean() * 100), 1)


# ------------------------------------------------------------------ main
def main():
    t = Table()
    rules = json.loads((OUT / "rules_search.json").read_text())
    rules.sort(key=lambda r: -r["train_mean"])
    seen, pats = set(), []
    for r in rules:
        k = (r["h"], tuple(sorted(r["rule"])))
        if k in seen:
            continue
        seen.add(k)
        pats.append(r)
    report = {"rules": [], "model": [], "breadth": [], "target_per_month": 7500}

    print("=== STEP 3: ONE $15,000 ticket a day, OOS 2025-08-01 .. "
          f"2026-07-31 ({t.ndays(1)} days) ===\n")
    print(f"{'#':>2} {'h':>5} {'tkt':>4} {'$/tkt':>8} {'total':>9} {'$/mo':>7} "
          f"{'mo+':>5} {'maxDD':>9} {'rand$':>7} {'pct':>5} {'inv$':>8} "
          f"{'train$':>8}  rule")
    for n, r in enumerate(pats):
        h = r["h"]
        m = apply_rule(t, r["rule"], h)
        sc = np.where(m, rule_margin(t, r["rule"]), -np.inf)
        oos = np.isin(t.split, 1)
        rows = pick(t, m & oos, sc, per="day")
        if rows.size < 20:
            continue
        res = score_rows(t, rows, h, 1, " AND ".join(r["rule"]))
        elig = t.mask(split=1, dec=RTH, h=h)
        nul = random_null(t, elig, h, 1, rows)
        nul2 = random_null(t, elig, h, 1, rows, fix_slots=False)
        inv = pick(t, m & oos, np.where(m, -sc, -np.inf), per="day")
        res.update(rule=r["rule"], seed=r["seed"], train_mean=r["train_mean"],
                   train_n=r["train_n"],
                   random_same_slots=round(nul["per_ticket_mean"], 2),
                   random_sd=nul["per_ticket_sd"],
                   percentile_vs_random=pctile(res["per_ticket"], nul["_vals"]),
                   random_any_slot=round(nul2["per_ticket_mean"], 2),
                   percentile_vs_random_any=pctile(res["per_ticket"],
                                                   nul2["_vals"]),
                   inverted_per_ticket=round(float(t.pnl[h][inv].mean()), 2)
                   if inv.size else None)
        a = pick(t, m & np.isin(t.split, 2), sc, per="day")
        res["aug2026"] = {"tickets": int(a.size),
                          "total": round(float(t.pnl[h][a].sum()), 2)
                          if a.size else 0.0}
        report["rules"].append(res)
        print(f"{n:>2} {h:>5} {res['tickets']:>4} {res['per_ticket']:>8.2f} "
              f"{res['total']:>9,.0f} {res['per_month']:>7.0f} "
              f"{res['months_pos']:>5} {res['max_dd']:>9,.0f} "
              f"{res['random_same_slots']:>7.2f} "
              f"{res['percentile_vs_random']:>5.1f} "
              f"{(res['inverted_per_ticket'] or 0):>8.2f} "
              f"{r['train_mean']:>8.1f}  {' AND '.join(r['rule'])}")

    # ---- model, walk-forward ------------------------------------------
    print("\n=== STEP 3b: walk-forward LightGBM, ONE ticket a day ===")
    for f in sorted(OUT.glob("model_scores_*.npy")):
        sc0 = np.load(f).astype(np.float64)
        h = f.stem.split("_")[2]
        m = t.mask(split=None, dec=RTH, h=h) & np.isfinite(sc0)
        sc = np.where(m, sc0, -np.inf)
        oos = np.isin(t.split, 1)
        # a model has no "firing time", so the ticket is taken at the FIRST
        # RTH decision time -- 09:35 -- which is the only causal choice.
        first = t.dec_i == t.dec.index("09:35")
        rows = pick(t, m & oos & first, sc, per="day")
        res = score_rows(t, rows, h, 1, f.stem)
        elig = t.mask(split=1, dec=["09:35"], h=h)
        nul = random_null(t, elig, h, 1, rows)
        inv = pick(t, m & oos & first, np.where(m, -sc0, -np.inf), per="day")
        res.update(random_same_slots=nul["per_ticket_mean"],
                   random_sd=nul["per_ticket_sd"],
                   percentile_vs_random=pctile(res["per_ticket"], nul["_vals"]),
                   inverted_per_ticket=round(float(t.pnl[h][inv].mean()), 2)
                   if inv.size else None)
        a = pick(t, m & np.isin(t.split, 2) & first, sc, per="day")
        res["aug2026"] = {"tickets": int(a.size),
                          "total": round(float(t.pnl[h][a].sum()), 2)
                          if a.size else 0.0}
        report["model"].append(res)
        print(f"{f.stem:>32} {h:>5} {res['tickets']:>4} "
              f"{res['per_ticket']:>8.2f} {res['total']:>9,.0f} "
              f"{res['per_month']:>7.0f} {res['months_pos']:>5} "
              f"{res['max_dd']:>9,.0f} rand={res['random_same_slots']:>7.2f} "
              f"pct={res['percentile_vs_random']:>5.1f} "
              f"inv={(res['inverted_per_ticket'] or 0):>7.2f}")
        if "shuf" in f.stem:
            continue
        # ---- STEP 4 breadth on the model: top-k at EVERY RTH slot
        for k in (3, 5, 10):
            rk = pick(t, m & oos, sc, topk=k, per="slot")
            b = score_rows(t, rk, h, 1, f"{f.stem}_top{k}_allslots")
            nb = random_null(t, t.mask(split=1, dec=RTH, h=h), h, 1, rk,
                             topk=k, n=NRAND_K)
            b.update(topk=k, random_same_slots=nb["per_ticket_mean"],
                     percentile_vs_random=pctile(b["per_ticket"], nb["_vals"]))
            report["breadth"].append(b)

    # ---- STEP 4 on the rules: top-k a day ------------------------------
    for r in report["rules"][:4]:
        h = r["h"]
        m = apply_rule(t, r["rule"], h)
        sc = np.where(m, rule_margin(t, r["rule"]), -np.inf)
        oos = np.isin(t.split, 1)
        for k in (3, 5, 10):
            rk = pick(t, m & oos, sc, topk=k, per="slot")
            b = score_rows(t, rk, h, 1,
                           (" AND ".join(r["rule"]))[:40] + f" top{k}")
            nb = random_null(t, t.mask(split=1, dec=RTH, h=h), h, 1, rk,
                             topk=k, n=NRAND_K)
            b.update(topk=k, rule=r["rule"],
                     random_same_slots=nb["per_ticket_mean"],
                     percentile_vs_random=pctile(b["per_ticket"], nb["_vals"]))
            report["breadth"].append(b)

    print("\n=== STEP 4: breadth -- top-k at EVERY regular-session slot ===")
    print(f"{'label':>44} {'k':>3} {'tkt':>6} {'$/tkt':>8} {'$/mo':>9} "
          f"{'mo+':>6} {'rand':>8} {'pct':>5}")
    for b in report["breadth"]:
        print(f"{b['label'][:44]:>44} {b['topk']:>3} {b['tickets']:>6} "
              f"{b['per_ticket']:>8.2f} {b['per_month']:>9.0f} "
              f"{b['months_pos']:>6} {b['random_same_slots']:>8.2f} "
              f"{b['percentile_vs_random']:>5.1f}")

    write_json("oos_report.json", report)
    print("\nwritten data/massive/wn/oos_report.json")


if __name__ == "__main__":
    main()
