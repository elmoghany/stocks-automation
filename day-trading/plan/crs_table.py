"""COST-RESCORE: print plan/crs_rescore.json as markdown tables."""
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
R = json.loads((HERE / "crs_rescore.json").read_text())
GRID = ["0", "2", "3", "4", "6", "8", "10", "12"]
only = sys.argv[1].split(",") if len(sys.argv) > 1 else None


def f(v, d=0):
    if v is None:
        return "—"
    if isinstance(v, str):
        return v
    return f"{v:+,.{d}f}"


def yv(s, k):
    y = s.get(k)
    if isinstance(y, dict):
        return y.get("per_month")
    return None


for nm, r in R.items():
    if only and not any(o in nm for o in only):
        continue
    print(f"\n#### {nm}\n")
    print("| bps/side | $/ticket | tkts/day | $/month | Y1 $/mo | Y2 $/mo | months + | ex-best-day | random $/tkt | pct vs random |")
    print("|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for b in GRID:
        s = r.get(b)
        if not isinstance(s, dict):
            continue
        y1, y2 = yv(s, "y1"), yv(s, "y2")
        if "oos_h1_per_ticket" in s:
            y1, y2 = f"H1 {s['oos_h1_per_ticket']:+.2f}/tkt", f"H2 {s['oos_h2_per_ticket']:+.2f}/tkt"
        exb = s.get("ex_best_day", s.get("ex_best_ticket_interp", s.get("ex_best_day_interp")))
        pc = s.get("pct_vs_random", s.get("pct_vs_random_normal_approx"))
        print(f"| {b} | {f(s.get('per_ticket'), 2)} | {s.get('tickets_per_day')} | {f(s.get('per_month'))} | "
              f"{f(y1)} | {f(y2)} | {s.get('months_pos', '—')} | {f(exb)} | {f(s.get('random_per_ticket'), 2)} | {f(pc, 1) if pc is not None else '—'} |")
    print(f"\nbreak-even bps/side: {r.get('breakeven_bps')}")
    for k in ("identity", "control_40d_flat_per_ticket", "inverted"):
        if k in r:
            print(f"{k}: {r[k]}")
