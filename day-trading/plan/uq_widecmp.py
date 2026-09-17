"""UNIVERSE+QUOTES (2026-09-16) -- constraint 1, stage 5: what the wider
universe is worth in dollars.

The comparison is deliberately narrow so that ONE thing differs. Same 150
trading days (every third session of the study window, so the sample
spans it uniformly rather than as a prefix), same nine regular-session
decision slots, same 32 causal features, same `wn_model` walk-forward
refitted monthly on rows strictly before each test month, same $15,000
ticket, same 10 bps/side + 50 bps extended cost ladder, same
20%-of-trailing-volume cap, same account-legal sequential simulator (one
position at a time, <= 7 tickets/day), same 30-seed random control.

The only difference is the CROSS-SECTION each day: 61 halal-PASS names
(plan/rl2/out) against 278 (plan/uq_out).

MARKET fills on both sides. The 1-second execution tape exists for the
incumbent 27,197 symbol-days, not for the widened 124,687, so pricing the
widened side with limit fills would compare a limit strategy against a
market strategy and attribute the difference to the universe. What the
limit entry is worth is measured separately, on the incumbent universe,
in Part 3 of universe-quotes-audit.md; the two effects are reported
separately and never multiplied together.

Usage: python plan/uq_widecmp.py [--h h30] [--seeds 30] [--postk 3]
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import uq_fills as UF                                         # noqa: E402
import uq_strat as US                                         # noqa: E402
import wn_lib                                                 # noqa: E402
from wn_lib import Table, summarize                           # noqa: E402

OUT = HERE / "uq_out"
RL2 = HERE / "rl2" / "out"


def run_side(tab_path, days_dir, feat_dir, score_path, dates, seeds,
             post_k, h, max_tickets, label):
    UF.DAYS, UF.FEAT = days_dir, feat_dir
    t = Table(tab_path)
    sc = np.load(score_path).astype(float)
    keep = [d for d in dates if d in set(t.dates)]
    keep = [d for d in keep
            if np.isfinite(sc[t.date_i == t.dates.index(d)]).any()]
    fin = np.isfinite(sc)
    scores = [sc, -sc] + [np.where(fin, np.random.default_rng(3000 + s)
                                   .random(len(sc)), np.nan)
                          for s in range(seeds)]
    kw = dict(offset=0.0, wait=1, post_k=post_k, h=h, exit_bps=UF.FEE_BPS,
              passive_bps=0.0, max_tickets=max_tickets, market=True)
    print(f"[{label}] {len(keep)} days, {len(t.syms)} symbols in the table",
          flush=True)
    acc = US.run_many(t, keep, scores, [kw])
    nd = len(keep)
    out = {"label": label, "days": nd, "symbols": len(t.syms),
           "names_per_day": round(float(np.mean(
               [np.sum((t.date_i == t.dates.index(d)) & t.printed_m
                       & (t.dec_i == UF.DEC_ET.index("09:35")))
                for d in keep])), 1),
           "model": US._summ(acc[(0, 0)], nd, "model"),
           "inverted": US._summ(acc[(0, 1)], nd, "inverted")}
    rnd = [US._summ(acc[(0, 2 + s)], nd, "") for s in range(seeds)]
    pt = np.array([x["per_ticket"] for x in rnd])
    pm = np.array([x["per_month"] for x in rnd])
    out["random"] = {"seeds": seeds,
                     "per_ticket_mean": round(float(pt.mean()), 2),
                     "per_ticket_sd": round(float(pt.std(ddof=1)), 2),
                     "per_month_mean": round(float(pm.mean()), 1),
                     "per_month_sd": round(float(pm.std(ddof=1)), 1)}
    out["edge_vs_random"] = round(out["model"]["per_ticket"]
                                  - float(pt.mean()), 2)
    out["percentile_vs_random_per_month"] = round(
        100.0 * float(np.mean(pm < out["model"]["per_month"])), 1)
    return out


def main(h="h30", seeds=30, post_k=3, max_tickets=7):
    wide_tab = OUT / "wn_s3" / "table.npz"
    wide_sc = OUT / "wn_s3" / f"model_scores_{h}_s0.npy"
    if not wide_sc.exists():
        raise SystemExit(f"run uq_wide.py --stage model first ({wide_sc})")
    zw = np.load(wide_tab, allow_pickle=False)
    dates = [str(x) for x in zw["dates"]]
    rep = {"h": h, "post_k": post_k, "seeds": seeds,
           "dates": len(dates), "first": dates[0], "last": dates[-1]}
    rep["wide"] = run_side(wide_tab, OUT / "days_s3", OUT / "feat_s3",
                           wide_sc, dates, seeds, post_k, h, max_tickets,
                           "WIDENED 278/day")
    rep["narrow"] = run_side(wn_lib.TAB, HERE / "rl2" / "out" / "days",
                             HERE / "rl2" / "out" / "feat",
                             wn_lib.OUT / f"model_scores_{h}_s0.npy",
                             dates, seeds, post_k, h, max_tickets,
                             "INCUMBENT 61/day")
    rep["universe_widening_per_month"] = round(
        rep["wide"]["model"]["per_month"] - rep["narrow"]["model"]["per_month"],
        1)
    (OUT / f"widecmp_{h}_k{post_k}.json").write_text(
        json.dumps(rep, indent=1, default=str))
    for k in ("narrow", "wide"):
        v = rep[k]
        m = v["model"]
        print(f"{v['label']:>18}: {v['names_per_day']:>6.1f} names/day  "
              f"{m['tickets']:>5} tkts ({m['tickets_per_day']:.2f}/day) "
              f"${m['per_ticket']:>8.2f}/tkt ${m['per_month']:>9.0f}/mo "
              f"mo+ {m['months_pos']}  random ${v['random']['per_ticket_mean']:>7.2f}"
              f"  edge ${v['edge_vs_random']:+6.2f}  pct "
              f"{v['percentile_vs_random_per_month']}")
    print(f"universe widening is worth "
          f"${rep['universe_widening_per_month']:+,.0f}/month on this sample")
    return rep


if __name__ == "__main__":
    a = sys.argv
    g = lambda f, d: (type(d)(a[a.index(f) + 1]) if f in a else d)  # noqa: E731
    main(g("--h", "h30"), g("--seeds", 30), g("--postk", 3),
         g("--maxtkt", 7))
