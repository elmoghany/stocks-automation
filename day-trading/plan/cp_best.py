"""CHAMPION-REPLAY: the closest miss, in full.

Runs the two rows the ablation and the 30-seed controls singled out --
`R1` (coil rank) and `R4` (coil rank, no -8% stop) -- plus the
champion-mimic reference, and prints what the index header asks for:
per-YEAR split, per-month table, drawdown, hold time, exit mix, and the
same numbers under the measured toll.

    python plan/cp_best.py
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cp_lib as L                                          # noqa: E402
import cp_run as R                                          # noqa: E402

OUT = L.ROOT / "data/massive/cp"
Y1_END = "2025-08-01"          # the repo's y2025 / year label boundary

ROWS = {
    "R4 coil + no stop": dict(rank="coil", stop_pct=None),
    "R1 coil rank only": dict(rank="coil"),
    "CHAMPION-MIMIC": {},
}


def split(legs, lo, hi):
    return [x for x in legs if lo <= x["date"] < hi]


def block(legs, label):
    if not legs:
        return f"| {label} | 0 | | | | | |"
    f = np.array([x["net_flat"] for x in legs])
    m = np.array([x["net_meas"] for x in legs])
    byday = defaultdict(float)
    for x in legs:
        byday[x["date"]] += x["net_flat"]
    mon = defaultdict(float)
    for d, v in byday.items():
        mon[d[:7]] += v
    cur = 0.0
    peak = 0.0
    dd = 0.0
    for d in sorted(byday):
        cur += byday[d]
        peak = max(peak, cur)
        dd = min(dd, cur - peak)
    return (f"| {label} | {len(legs)} | {f.mean():+.2f} | {m.mean():+.2f} | "
            f"{f.sum():+,.0f} | {f.sum()/max(len(mon),1):+,.0f} | "
            f"{sum(1 for k in mon if mon[k] > 0)}/{len(mon)} | {dd:+,.0f} |")


def main():
    ds = R.dates()
    res = R.run_batch(ds, dict(ROWS))
    print("\n## The closest miss, split every way the bar asks for\n")
    print("| row / window | tickets | flat10 $/tkt | measured $/tkt | "
          "total flat10 | $/month | months + | max drawdown |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|")
    for name in ROWS:
        legs = res[name]["_legs"]
        print(block(legs, f"**{name}** -- whole window"))
        print(block(split(legs, "0000", Y1_END), f"{name} -- year 1 "
                                                 f"(to {Y1_END})"))
        print(block(split(legs, Y1_END, "9999"), f"{name} -- year 2"))
    best = res["R4 coil + no stop"]["_legs"]
    mon = defaultdict(float)
    for x in best:
        mon[x["date"][:7]] += x["net_flat"]
    print("\nR4 by month (flat 10 bps): " +
          "  ".join(f"{k} {v:+,.0f}" for k, v in sorted(mon.items())))
    ex = defaultdict(lambda: [0, 0.0])
    hold = []
    for x in best:
        k = x["reason"].split()[0]
        ex[k][0] += 1
        ex[k][1] += x["net_flat"]
        hold.append(x["exit_min"] - x["entry_min"])
    print("\nR4 exits: " + "  ".join(
        f"{k} {v[0]}/{v[1]:+,.0f}" for k, v in sorted(ex.items())))
    print(f"R4 hold minutes: median {np.median(hold):.0f}, "
          f"mean {np.mean(hold):.0f}")
    p = sorted(x["net_flat"] for x in best)
    gp = sum(v for v in p if v > 0) or 1
    print(f"R4 win rate {100*np.mean([v > 0 for v in p]):.1f}%, "
          f"median leg {np.median(p):+.1f}, profit factor "
          f"{gp/abs(sum(v for v in p if v < 0)):.3f}, top-10 legs "
          f"{sum(p[-10:])/gp*100:.0f}% of gross profit")
    (OUT / "best.json").write_text(json.dumps(R._strip(res), indent=1,
                                              default=float))


if __name__ == "__main__":
    main()
