"""CLOSE-MOMENTUM (2026-09-16): build the audit's tables from the JSONs.

Every table in close-momentum-audit.md is printed by this file, so a
number in the prose can be traced to the artifact that produced it. Run
it after cm_etf_study / cm_single / cm_configs / cm_controls / cm_rev /
cm_model / cm_honesty.

Usage:  python plan/cm_report.py > data/massive/cm/report.md
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "rl2"))
import cm_lib as L                                            # noqa: E402

OUT = L.OUT


def j(name):
    p = OUT / name
    return json.loads(p.read_text()) if p.exists() else None


def t1_etf():
    d = j("etf_study.json")
    print("\n### T1. The published effect on the halal index ETFs "
          "(and SPY as the reference)\n")
    print("| ETF | n | slope on r_first | t | slope on r_2last | t | "
          "mean last-half-hour return | sign-match r_first |")
    print("|---|---|---|---|---|---|---|---|")
    for s, r in d["regressions"].items():
        a, b = r["r_last ~ r_first"], r["r_last ~ r_2last"]
        print(f"| {s} | {a['n']} | {a['slope']:+.4f} | {a['t']:+.2f} | "
              f"{b['slope']:+.4f} | {b['t']:+.2f} | "
              f"{r['mean_r_last_bps']:+.2f} bp | "
              f"{r['sign_match_first']*100:.1f}% |")
    print("\n| ETF row (one $15k ticket/day, 15:30 open -> 15:59 close) | n | "
          "$/ticket | $/month | Y1 | Y2 |")
    print("|---|---|---|---|---|---|")
    for k, v in d["trade_rows"].items():
        if not k.endswith("15:59"):
            continue
        if not any(k.startswith(x) for x in ("SPUS|", "HLAL|", "SPY|")):
            continue
        a = v["all"]
        print(f"| {k} | {a['tickets']} | {a['per_ticket']:+.2f} | "
              f"{a['per_month']:+.1f} | {v['y1']['per_ticket']:+.2f} | "
              f"{v['y2']['per_ticket']:+.2f} |")


def t2_uncond():
    d = j("gross_profile_wide.json")
    print("\n### T2. Unconditional expectancy per eligible row, "
          "causal wide universe, 448 days\n")
    print("| entry -> exit | rows | gross bp | se | t | net bp | "
          "net $ on $15k | Y1 gross bp | Y2 gross bp |")
    print("|---|---|---|---|---|---|---|---|---|")
    for k, v in d.items():
        t = v["gross_bps"] / max(v["gross_bps_se"], 1e-9)
        print(f"| {k} | {v['rows']:,} | {v['gross_bps']:+.2f} | "
              f"{v['gross_bps_se']:.2f} | {t:+.2f} | {v['net_bps']:+.2f} | "
              f"{v['net_$_on_15k']:+.2f} | {v['y1_gross_bps']:+.2f} | "
              f"{v['y2_gross_bps']:+.2f} |")


def t3_configs(uni="wide", n=20):
    d = j(f"configs_{uni}.json")
    rows = sorted(d.items(), key=lambda kv: -kv[1]["all"]["per_month"])
    print(f"\n### T3. Top {n} of {len(d)} pre-registered configs on "
          f"`{uni}` by $/month\n")
    print("| config | tickets | total | $/ticket | $/month | Y1 $/tkt | "
          "Y2 $/tkt | aug2026 $/tkt | months + | best | ex-best | maxDD |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for k, v in rows[:n]:
        a = v["all"]
        print(f"| {k} | {a['tickets']} | {a['total']:+,.0f} | "
              f"{a['per_ticket']:+.2f} | "
              f"{a['per_month']:+.1f} | {v['y1']['per_ticket']:+.2f} | "
              f"{v['y2']['per_ticket']:+.2f} | "
              f"{v['aug2026']['per_ticket']:+.2f} | {a['months_pos']} | "
              f"{a['best']:+,.0f} | "
              f"{a['ex_best_total']:+,.0f} | {a['max_dd']:+,.0f} |")
    pt = [v["all"]["per_ticket"] for _, v in rows]
    print(f"\nmedian $/ticket over all {len(rows)} configs: "
          f"**{np.median(pt):+.2f}**")


def t4_controls(uni="wide"):
    d = j(f"controls_{uni}.json")
    print(f"\n### T4. Controls on `{uni}`\n")
    print("| config | tickets | $/ticket | $/month | random $/tkt | "
          "edge | pct total | pct ex-best | inverted | shuffled | "
          "daily t | $/month p5 |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for k, r in d.items():
        a = r["row"]["all"]
        b = r["bootstrap"]
        print(f"| {k} | {a['tickets']} | {a['per_ticket']:+.2f} | "
              f"{a['per_month']:+.1f} | "
              f"{r['random']['mean_per_ticket']:+.2f} | "
              f"{r['edge_vs_random_per_ticket']:+.2f} | "
              f"{r['pctile_total']} | {r['pctile_ex_best']} | "
              f"{r['inverted']['per_ticket']:+.2f} | "
              f"{r['shuffled']['mean_per_ticket']:+.2f} | "
              f"{b.get('daily_t', 0):+.2f} | "
              f"{b.get('per_month_p5', 0):+,.0f} |")


def t5_rev(uni="wide"):
    d = j(f"rev_{uni}.json")
    print(f"\n### T5. The late-session REVERSAL composite on `{uni}` "
          "(sign and membership from Y1 only)\n")
    print("| entry -> exit | k | tickets | $/ticket | $/month | Y1 | Y2 | "
          "aug2026 | random | edge | pct | inverted | shuffled | t |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for pair, v in d.items():
        for k in ("k1", "k3", "k7"):
            if k not in v:
                continue
            r = v[k]
            a = r["row"]["all"]
            print(f"| {pair} | {k[1:]} | {a['tickets']} | "
                  f"{a['per_ticket']:+.2f} | {a['per_month']:+.1f} | "
                  f"{r['row']['y1']['per_ticket']:+.2f} | "
                  f"{r['row']['y2']['per_ticket']:+.2f} | "
                  f"{r['row']['aug2026']['per_ticket']:+.2f} | "
                  f"{r['random']['mean_per_ticket']:+.2f} | "
                  f"{r['edge_vs_random_per_ticket']:+.2f} | "
                  f"{r['pctile_total']} | "
                  f"{r['inverted']['per_ticket']:+.2f} | "
                  f"{r['shuffled']['mean_per_ticket']:+.2f} | "
                  f"{r['bootstrap'].get('daily_t', 0):+.2f} |")


def t6_ic():
    d = j("model_wide.json")["ic"]
    print("\n### T6. Rank IC of every causal feature vs the ticket's "
          "realized net return\n")
    for pair, row in d.items():
        items = sorted(((abs(v["all"]), f, v) for f, v in row.items()
                        if f != "_n"), reverse=True)[:8]
        print(f"\n**{pair}**  (n = {row['_n']:,})\n")
        print("| feature | IC all | IC Y1 | IC Y2 |")
        print("|---|---|---|---|")
        for _, f, v in items:
            print(f"| {f} | {v['all']:+.4f} | {v['y1']:+.4f} | "
                  f"{v['y2']:+.4f} |")


def t7_model():
    d = j("model_wide.json")
    print("\n### T7. LightGBM fitted on Y1 only, read on Y2 "
          "(3 seeds, real target vs shuffled target)\n")
    print("| entry -> exit | target | seed | k | Y2 tickets | Y2 $/ticket | "
          "Y2 $/month | IC on Y2 |")
    print("|---|---|---|---|---|---|---|---|")
    for key, v in d.items():
        if not key.startswith("model|"):
            continue
        pair = key.split("|", 1)[1]
        for tag in ("real", "shuffled"):
            for row in v[tag]:
                a = row["y2"]
                print(f"| {pair} | {tag} | {row['seed']} | {row['topk']} | "
                      f"{a['tickets']} | {a['per_ticket']:+.2f} | "
                      f"{a['per_month']:+.1f} | {row['ic_y2']:+.4f} |")


def t8_honesty():
    d = j("honesty_wide.json")
    print("\n### T8. The adversarial battery\n")
    p = d["poison"]
    print(f"- **poison** (garbage on every bar after the decision minute, "
          f"{p['days']} days x {len(p['cuts'])} cut points "
          f"{p['cuts']}): **{p['array_checks']} array checks / "
          f"{p['array_mismatches']} mismatches**, "
          f"**{p['pick_checks']} selection checks / "
          f"{p['pick_mismatches']} mismatches**")
    b = d["battery"]
    print(f"- **hold-is-zero**: {b['hold_zero']['tickets']} tickets, "
          f"${b['hold_zero']['total']:.2f}")
    c = b["cost_monotone"]
    print(f"- **cost monotone**: 0x ${c['zero']:,.0f} > 1x "
          f"${c['modelled']:,.0f} > 10x ${c['ten_x']:,.0f} -> "
          f"{b['cost_monotone_ok']}")
    for k, v in b.items():
        if k.startswith("foresight"):
            print(f"- **{k}**: {v['tickets']} tickets, "
                  f"${v['per_ticket']:+,.2f}/ticket, "
                  f"${v['per_month']:+,.0f}/month")
    i = d["identity"]
    print(f"- **identity gate**: {i['tickets_recomputed']:,} tickets "
          f"recomputed from (px_in, px_out, shares, minutes) alone, "
          f"{i['mismatches']} mismatches, worst |diff| "
          f"${i['worst_abs_diff']}")
    e = d["early_close"]
    print(f"- **early closes**: {e['n_half_days']} half days in the window "
          f"({', '.join(sorted(e['half_days_in_window']))}); eligible rows on "
          f"them: {e['eligible_rows_at_15:30_on_half_days']} at 15:30, "
          f"{e['eligible_rows_at_15:00_on_half_days']} at 15:00, "
          f"{e['eligible_rows_at_12:00_on_half_days']} at 12:00")


def t9_cost():
    d = j("rev_cost_wide.json")
    if not d:
        return
    print("\n### T9. What the toll is worth: the same composite at "
          "different fee ladders\n")
    print("| config | fee bps/side | tickets | $/ticket | $/month | Y1 | Y2 |")
    print("|---|---|---|---|---|---|---|")
    for cfg, rows in d.items():
        for fee, v in rows.items():
            print(f"| {cfg} | {fee} | {v.get('tickets','')} | "
                  f"{v['per_ticket']:+.2f} | "
                  f"{v.get('per_month', 0):+.1f} | "
                  f"{v.get('y1', 0):+.2f} | {v.get('y2', 0):+.2f} |")


if __name__ == "__main__":
    t1_etf()
    t2_uncond()
    t3_configs("wide")
    t4_controls("wide")
    t5_rev("wide")
    t6_ic()
    t7_model()
    t8_honesty()
    t9_cost()
    if (OUT / "configs_gap.json").exists():
        t3_configs("gap", 12)
        t4_controls("gap")
