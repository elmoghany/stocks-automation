"""LIMIT-EXEC: render the audit tables from plan/lx_out/*.json.

Usage: python plan/lx_report.py [--frame frame_ladderA_h30.json]
                                [--wn tables_wn.json] [--rev tables_rev.json]
                                [--veto tables_veto.json] [--orb orb_wide.json,orb_pool.json]
Prints markdown; nothing is computed here that is not in the json files.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "lx_out"
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def load(name):
    p = OUT / name
    return json.loads(p.read_text()) if p.exists() else None


def f2(x, sign=True):
    if x is None:
        return "—"
    return f"{x:+,.2f}" if sign else f"{x:,.2f}"


def frame_table(j):
    if not j:
        return "_(frame pass not landed)_"
    rows = j["rows"]
    out = ["| config (entry / exit) | fill rate | tkts/day | **flat $/tkt** (±seed sd) | $/month @flat | measured $/tkt | zero-cost $/tkt | market CF (same names) | entry passive share | exit passive share | months + | ex-best | aug2026 | foresight $/tkt | anti |",
           "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|"]
    for nm, r in rows.items():
        fl = r["fills"]
        aug = r["flat"].get("aug2026", {})
        out.append(
            f"| `{nm}` | {fl.get('fill_rate', 0):.3f} | {r['tickets_per_day']:.2f} | "
            f"**{f2(r['flat']['per_ticket_mean'])}** ± {r['flat']['per_ticket_sd']:.1f} | "
            f"{f2(r['flat']['per_month_mean'])} | {f2(r['meas']['per_ticket_mean'])} | "
            f"{f2(r['zero']['per_ticket_mean'])} | {f2(r.get('mkt_counterfactual_flat'))} | "
            f"{fl.get('entry_passive_frac_mean', 0):.2f} | {fl.get('exit_passive_frac_mean', 0):.2f} | "
            f"{r['flat']['months_pos']} | {f2(r['flat']['ex_best'])} | "
            f"{aug.get('tickets', 0)} tk {f2(aug.get('total'))} | "
            f"{f2(r.get('fore', {}).get('flat'))} | {f2(r.get('anti', {}).get('flat'))} |")
    return "\n".join(out)


def decomp_table(j, which="rows", label=""):
    if not j:
        return "_(not landed)_"
    out = [f"| {label} config | leg | n passive fills | price improvement (bps) | 5-min markout (bps) | **net** (bps) | share reverted | reverted: pi / mo | way-down: pi / mo | partial share | median wait (s) |",
           "|---|---|---:|---:|---:|---:|---:|---|---|---:|---:|"]
    for nm, r in j[which].items():
        d = r.get("decomp", {})
        for leg, lab in (("e", "entry (buy at bid)"), ("x", "exit (sell at ask)")):
            e = d.get(leg, {})
            if not e.get("n"):
                continue
            out.append(
                f"| `{nm}` | {lab} | {e['n']:,} | {e['pi_bps_mean']:+.2f} | {e['markout5_bps_mean']:+.2f} | "
                f"**{e['net_bps']:+.2f}** | {e['share_reverted']:.3f} | "
                f"{e['reverted']['pi']:+.1f} / {e['reverted']['mo']:+.1f} | "
                f"{e['way_down']['pi']:+.1f} / {e['way_down']['mo']:+.1f} | "
                f"{e['partial_share']:.3f} | {e['wait_s_median']:.0f} |")
    return "\n".join(out)


def tables_table(j, title):
    if not j:
        return f"_({title}: not landed)_"
    out = [f"**{title}** — {j['days']} days, {j['seeds']} random seeds",
           "",
           "| ladder | policy | tickets | tkts/day | fill rate | **flat $/tkt** | $/month | edge vs random | pct | measured $/tkt | edge (meas) | pct (meas) | zero | months + | ex-best | y1 / y2 $/tkt | aug2026 |",
           "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---|---|"]
    for lad, r in j["rows"].items():
        rd = r["random"]
        out.append(f"| `{lad}` | random ×{j['seeds']} | | {rd['tickets_per_day']:.2f} | | "
                   f"{f2(rd['flat']['per_ticket_mean'])} ± {rd['flat']['per_ticket_sd']:.1f} | "
                   f"{f2(rd['flat']['per_month_mean'])} | — | — | {f2(rd['meas']['per_ticket_mean'])} | — | — | "
                   f"{f2(rd['zero']['per_ticket_mean'])} | | | | |")
        for nm, v in r.items():
            if nm == "random":
                continue
            fl, m, z = v["flat"], v["meas"], v["zero"]
            aug = fl.get("aug2026", {})
            out.append(f"| | {nm} | {fl['tickets']} | {fl['tickets_per_day']:.2f} | {v['fills'].get('fill_rate', 0):.3f} | "
                       f"**{f2(fl['per_ticket'])}** | {f2(fl['per_month'])} | {f2(fl['edge_vs_random'])} | {fl['percentile']:.0f} | "
                       f"{f2(m['per_ticket'])} | {f2(m['edge_vs_random'])} | {m['percentile']:.0f} | {f2(z['per_ticket'])} | "
                       f"{fl['months_pos']} | {f2(fl['ex_best'])} | {f2(fl['y1']['per_ticket'])} / {f2(fl['y2']['per_ticket'])} | "
                       f"{aug.get('tickets', 0)} tk {f2(aug.get('total'))} |")
    return "\n".join(out)


def orb_table(j):
    if not j:
        return "_(not landed)_"
    out = [f"**ORB / {j['universe']}** — {j['days']} days (stride {j.get('stride', 1)}), "
           f"{j['breakers_per_day']:.1f} breakers/day of {j['names_per_day']:.1f} names, {j['seeds']} seeds",
           "",
           "| ladder | tkts/day | fill | random flat $/tkt | random meas | random zero | market CF | strength $/tkt (pct) | weak (pct) | foresight | entry pi / mo | exit pi / mo |",
           "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|"]
    for lad, r in j["rows"].items():
        d = r["decomp"]
        e, x = d.get("e", {}), d.get("x", {})
        fe = f"{e.get('pi_bps_mean', 0):+.1f} / {e.get('markout5_bps_mean', 0):+.1f}" if e.get("n") else "—"
        fx = f"{x.get('pi_bps_mean', 0):+.1f} / {x.get('markout5_bps_mean', 0):+.1f}" if x.get("n") else "—"
        fl = r["flat"]
        out.append(f"| `{lad}` | {r['tickets_per_day']:.2f} | {r['fills'].get('fill_rate', 0):.3f} | "
                   f"**{f2(fl['random_per_ticket_mean'])}** ± {fl['random_per_ticket_sd']:.1f} | "
                   f"{f2(r['meas']['random_per_ticket_mean'])} | {f2(r['zero']['random_per_ticket_mean'])} | "
                   f"{f2(r.get('mkt_counterfactual_flat'))} | {f2(fl['strength']['per_ticket'])} ({fl['strength']['percentile']:.0f}) | "
                   f"{f2(fl['weak']['per_ticket'])} ({fl['weak']['percentile']:.0f}) | {f2(fl['fore']['per_ticket'])} | {fe} | {fx} |")
    return "\n".join(out)


def main():
    a = sys.argv
    g = lambda f, d: (a[a.index(f) + 1] if f in a else d)  # noqa: E731
    fr = load(g("--frame", "frame_ladderA_h30.json"))
    print("## FRAME\n")
    print(frame_table(fr))
    print("\n## ADVERSE (frame)\n")
    print(decomp_table(fr, "rows", "frame"))
    for key, name, title in (("--wn", "tables_wn.json", "WIDE-NET / UQ relabel / LX refit (OOS year, post 3, h30)"),
                             ("--rev", "tables_rev.json", "CLOSE-MOMENTUM REV 15:30→15:59, k = 7"),
                             ("--veto", "tables_veto.json", "CATALYST veto ANY_NEG_3d, 1/day @09:35, h60 (random on the vetoed universe)")):
        print(f"\n## {title}\n")
        print(tables_table(load(g(key, name)), title))
    for name in g("--orb", "orb_wide.json,orb_pool.json").split(","):
        print("\n## ORB\n")
        print(orb_table(load(name)))


if __name__ == "__main__":
    main()
