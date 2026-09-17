"""OPEN-UNIVERSE (2026-09-17) TEST 5: put the halal screen back, post hoc.

USER DIRECTION (2026-09-17) was "IGNORE whether the stock is halal for now",
because the gate is being repaired separately.  The mandate's own condition
is that any policy which reaches the bar or comes within 2x of it must then be
re-run with the halal list applied, so the user knows what would actually be
tradeable.

TWO WAYS TO APPLY IT, and they answer different questions:
  screen   the policy re-ranks INSIDE the halal subset -- it takes its best 7
           halal names.  This is what the account would really do.
  filter   the policy keeps its original picks and simply drops the ones that
           are not halal, trading fewer tickets.  This isolates how much of
           the edge lived in the names the screen removes.

WHICH LIST.  data/halal_list.json (415 names, gate of 2026-09-16) and
data/halal_list.NEW.json when it differs.  On 2026-09-17 the two are
IDENTICAL (415 symbols, same set), so only one column is reported and that
fact is stated rather than implied.

CAVEAT, stated because it is the whole reason this is post hoc: the list is a
PRESENT-DAY snapshot, not point-in-time.  Every other line in this repo uses
`halal_pt` at the decision date.  A present-day list applied to 2024-2026
dates can only be indicative -- it is used here to answer "roughly how much
survives", not to produce a tradeable number.

Usage:  python plan/ou_halal.py
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ou_lib as L                                            # noqa: E402
import ou_cost as OC                                          # noqa: E402
import ou_frame as OF                                         # noqa: E402


def halal_set():
    a = set(json.loads((L.ROOT / "data" / "halal_list.json").read_text())
            ["symbols"])
    f = L.ROOT / "data" / "halal_list.NEW.json"
    b = set(json.loads(f.read_text())["symbols"]) if f.exists() else set()
    return a, b


def main():
    seeds = 30
    if "--seeds" in sys.argv:
        seeds = int(sys.argv[sys.argv.index("--seeds") + 1])
    cur, new = halal_set()
    same = (cur == new)
    dates = L.study_dates()
    syms, sidx, A = L.gd_matrices(dates)
    F = OF.build_features(A)
    dc = OC.DailyCost()
    uni = L.universe()
    MC = L.mcap_matrix(dates, syms, sidx)
    base = {
        "open": {d: {r[0] for r in uni[d]} for d in dates},
        "open_top600": {d: {r[0] for r in uni[d][:L.MINUTE_TOP]}
                        for d in dates},
    }
    for nm, lo_, hi_ in (("open_mcap10b", 10e9, np.inf),
                         ("open_mcap2_10b", 2e9, 10e9)):
        base[nm] = {d: {r[0] for r in uni[d]
                        if r[0] in sidx and lo_ <= MC[i, sidx[r[0]]] < hi_}
                    for i, d in enumerate(dates)}
    out = {"list_n": len(cur), "new_same_as_current": same,
           "union_halal_in_open": None, "rows": {}}
    u = sorted({r[0] for v in uni.values() for r in v})
    out["union_halal_in_open"] = int(sum(1 for x in u if x in cur))
    for uk, mem in list(base.items()):
        hm = {d: {s for s in v if s in cur} for d, v in mem.items()}
        n = np.array([len(v) for v in hm.values()])
        print(f"[halal] {uk:16s} halal names/day {n.min()}..{n.max()} "
              f"(mean {n.mean():.0f}) of "
              f"{np.mean([len(v) for v in mem.values()]):.0f}", flush=True)
        for cost in ("flat10", "zero", "measured"):
            pre = OF.Pre(dates, A, sidx, hm, "close", dc, syms)
            r = OF.search(pre, F, {"cost": cost, "exit_mode": "close",
                                   "long_only": True, "universe": uk},
                          seeds=seeds)
            lab = f"{uk}|HALAL-SCREEN|{cost}"
            out["rows"][lab] = r
            b = r["best"]
            print(f"[halal] {lab:36s} best ${b['per_month']:+9,.0f}/mo "
                  f"({b['label']:>12s}, ${b['per_ticket']:+7.2f}/tkt) "
                  f"Y1 {b['y1_per_month']} Y2 {b['y2_per_month']} random "
                  f"${r['random_per_month_mean']:+9,.0f} pct "
                  f"{r['pct_vs_random']}", flush=True)
    L.write("halal_posthoc.json", out)
    print("[halal] wrote plan/ou_out/halal_posthoc.json", flush=True)


if __name__ == "__main__":
    main()
