"""RL-SERIES v2 (2026-09-16): scoring against the STANDING LOOP BAR.

The user's bar, restated so every row in rl2-audit.md can be checked against
it mechanically:

  1. >= $7,500 per month NET of costs (10 bps/side + 50 bps extended),
     i.e. ~ >= $170,000 over the two-year window;
  2. BOTH years positive;
  3. >= 90th percentile of the 30-seed random control on TOTAL **and** on
     TOTAL EX-BEST-DAY (so one lucky session cannot carry a row);
  4. the corrected shuffled-labels control negative;
  5. the poison test passing;
  6. aug-2026 sign-consistent.

`score()` computes 1, 2, 3 and 6 for a trade list; 4 and 5 are properties of
the approach, not of a single row, and are asserted once per approach.

A "month" is 21 trading days, so $/month = total * 21 / n_test_days -- the
same convention for every row, including the controls.
"""
import numpy as np

DAYS_PER_MONTH = 21.0
BAR_PER_MONTH = 7500.0


def daily(trades, dates):
    by = {}
    for t in trades:
        by[t["date"]] = by.get(t["date"], 0.0) + t["pnl"]
    return np.array([by.get(d, 0.0) for d in dates], float)


def metrics(trades, dates, label=""):
    d = daily(trades, dates)
    n = len(dates)
    eq = np.concatenate([[0.0], np.cumsum(d)])
    dd = float((eq - np.maximum.accumulate(eq)).min())
    sd = float(d.std(ddof=1)) if n > 1 else 0.0
    tot = float(d.sum())
    best = float(d.max()) if n else 0.0
    ya = np.array([x for x, dt in zip(d, dates) if dt < "2026-01-01"])
    yb = np.array([x for x, dt in zip(d, dates) if dt >= "2026-01-01"])
    aug = np.array([x for x, dt in zip(d, dates) if dt >= "2026-08-01"])
    nt = len(trades)
    return {
        "label": label, "days": n, "tickets": nt,
        "total": round(tot, 2),
        "per_month": round(tot * DAYS_PER_MONTH / max(n, 1), 2),
        "per_ticket": round(tot / nt, 3) if nt else 0.0,
        "tickets_per_day": round(nt / max(n, 1), 2),
        "sharpe": round(d.mean() / sd * np.sqrt(252), 3) if sd else 0.0,
        "max_dd": round(dd, 2),
        "best_day": round(best, 2),
        "total_ex_best": round(tot - best, 2),
        "per_month_ex_best": round((tot - best) * DAYS_PER_MONTH / max(n, 1), 2),
        "y2025_total": round(float(ya.sum()), 2), "y2025_days": len(ya),
        "y2026_total": round(float(yb.sum()), 2), "y2026_days": len(yb),
        "aug2026_total": round(float(aug.sum()), 2), "aug2026_days": len(aug),
        "win_days": round(float((d > 0).mean()), 4) if n else 0.0,
        "ext_exit_pnl": round(sum(t["pnl"] for t in trades if t["ext_out"]), 2),
        "rth_exit_pnl": round(sum(t["pnl"] for t in trades
                                  if not t["ext_out"]), 2),
    }


def random_control(days, dates, exit_rule, p_entry, max_new, seeds=30,
                   step_mask=None, T=None):
    """30 uniform-score policies with the same eligibility, fills, costs and
    exit rule, at a matched entry probability. Returns per-seed totals and
    ex-best-day totals."""
    import sim as SM
    tot, exb, tk = [], [], []
    for s in range(seeds):
        tr = []
        for d in days:
            rng = np.random.default_rng(30_000 + s)
            sc = rng.random((T, d.S))
            if step_mask is not None:
                sc = np.where(step_mask[:, None], sc, -np.inf)
            tr += SM.run_day(d, sc, exit_rule, min_score=1.0 - p_entry,
                             max_new_per_step=max_new)[0]
        m = metrics(tr, dates)
        tot.append(m["total"])
        exb.append(m["total_ex_best"])
        tk.append(m["tickets_per_day"])
    return {"seeds": seeds, "total": tot, "total_ex_best": exb,
            "mean_total": round(float(np.mean(tot)), 2),
            "p90_total": round(float(np.percentile(tot, 90)), 2),
            "mean_total_ex_best": round(float(np.mean(exb)), 2),
            "p90_total_ex_best": round(float(np.percentile(exb, 90)), 2),
            "mean_tickets_per_day": round(float(np.mean(tk)), 2)}


def verdict(m, rc):
    """Does this row clear the bar? Booleans, no interpretation."""
    pt = 100.0 * float(np.mean(np.array(rc["total"]) < m["total"])) if rc else 0.0
    pe = 100.0 * float(np.mean(np.array(rc["total_ex_best"])
                               < m["total_ex_best"])) if rc else 0.0
    return {
        "per_month": m["per_month"],
        "passes_7500_per_month": bool(m["per_month"] >= BAR_PER_MONTH),
        "both_years_positive": bool(m["y2025_total"] > 0 and
                                    m["y2026_total"] > 0),
        "pct_vs_random_total": round(pt, 2),
        "pct_vs_random_ex_best": round(pe, 2),
        "passes_pct90_total": bool(pt >= 90.0),
        "passes_pct90_ex_best": bool(pe >= 90.0),
        "aug2026_sign_consistent": bool(
            m["aug2026_days"] == 0 or
            (m["aug2026_total"] > 0) == (m["total"] > 0)),
        "PASSES_BAR": bool(m["per_month"] >= BAR_PER_MONTH
                           and m["y2025_total"] > 0 and m["y2026_total"] > 0
                           and pt >= 90.0 and pe >= 90.0),
    }
