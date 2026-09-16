"""RL-SERIES v2 (2026-09-16): every landed row restated against the
STANDING LOOP BAR (>= $7,500/month net).

Rows written before plan/rl2/bar.py existed only carry a total and a day
count, so their $/month is total * 21 / days -- the same convention
bar.metrics uses, applied after the fact. Rows that DO carry a bar verdict
are printed with it.

  python plan/rl2/bar_table.py > plan/rl2/out/bar_table.md
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RES = HERE / "results"
OUT = HERE / "out"
BAR = 7500.0


def pm(total, days):
    return total * 21.0 / max(days, 1)


def main():
    rows = []
    # honesty + baselines
    h = json.loads((OUT / "honesty.json").read_text())
    b = json.loads((RES / "baselines.json").read_text())
    rows.append(["HOLD (never trade)", 255, 0.0, 0.0, 0.0, "reference"])
    for k in ("RANDOM-ANY", "RANDOM-SPREAD", "RANDOM-RTH", "RANDOM-RTH-greedy"):
        v = b[k]
        rows.append([f"{k} (30 seeds, mean)", 255, v["mean_total"],
                     pm(v["mean_total"], 255), v["mean_per_ticket"],
                     "control"])
    for f in sorted(RES.glob("*.json")):
        if f.name == "baselines.json" or f.name.startswith("rules_null"):
            continue
        d = json.loads(f.read_text())
        name = f.stem
        if "overall" in d:                       # bandit2 / rules2 style
            o = d["overall"]
            v = d.get("verdict", {})
            rows.append([name, o["days"], o["total"], o["per_month"],
                         o["per_ticket"],
                         f"pct{v.get('pct_vs_random_total','-')}"
                         f"/{v.get('pct_vs_random_ex_best','-')}"
                         + (" PASS" if v.get("PASSES_BAR") else "")])
        elif "heldout" in d:
            o = d["heldout"]
            v = d.get("verdict", {})
            rows.append([name + " :: heldout", o["days"], o["total"],
                         o.get("per_month", pm(o["total"], o["days"])),
                         o["per_ticket"],
                         f"pct{v.get('pct_vs_random_total','-')}"
                         f"/{v.get('pct_vs_random_ex_best','-')}"
                         + (" PASS" if v.get("PASSES_BAR") else "")])
        elif "walkforward" in d:
            o = d["walkforward"]
            v = d.get("verdict", {})
            rows.append([name + " :: wf", o["days"], o["total"],
                         o.get("per_month", pm(o["total"], o["days"])),
                         o["per_ticket"],
                         f"pct{v.get('pct_vs_random_total','-')}"
                         f"/{v.get('pct_vs_random_ex_best','-')}"
                         + (" PASS" if v.get("PASSES_BAR") else "")])
        elif "test" in d and isinstance(d["test"], dict):
            o = d["test"]
            rows.append([name + " :: test", o["days"], o["total"],
                         pm(o["total"], o["days"]), o["per_ticket"], ""])
        elif "total" in d:
            rows.append([name, d.get("days", 255), d["total"],
                         pm(d["total"], d.get("days", 255)),
                         d.get("per_ticket", 0.0), ""])
    rows.sort(key=lambda r: -r[3])
    print("| row | days | total $ | **$/month** | $/ticket | vs bar |")
    print("|---|---|---|---|---|---|")
    for n, d_, t, p, pt, note in rows:
        flag = "**PASSES**" if p >= BAR else ""
        print(f"| {n} | {d_} | {t:,.0f} | **{p:,.0f}** | {pt:.2f} | "
              f"{note} {flag} |")
    print(f"\nBar = ${BAR:,.0f}/month net. Rows above are every result file in "
          f"plan/rl2/results/.")


if __name__ == "__main__":
    main()
