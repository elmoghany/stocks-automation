"""CHAMPION-REPLAY: reprice the honest champion's ledger PER LEG.

COST-REBASE published the aggregate (C37F-hf2 -$55.08 gross ->
-$246.93 measured) but not a per-leg cost, and Part 2's question --
"what is a PERFECT day-type oracle worth?" -- is a question about a
SUBSET of the legs, so it needs one. This walks each stored leg back to
the minute panel and charges `cp_cost.TapeCost` at the entry and exit
minutes, then reports the oracle-veto ladder under all three tolls.

    python plan/cp_reprice.py [--tag C37F_hf2]
"""

import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cp_lib as L                                          # noqa: E402
import cp_cost as C                                         # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
GRID_START = 4 * 60


def _minute(ts):
    d = datetime.fromisoformat(ts)
    return d.hour * 60 + d.minute - GRID_START


def reprice(tag="C37F_hf2"):
    legs = json.loads(
        (ROOT / f"data/massive/rotation_trades_{tag}.json").read_text())
    pool = {}
    for lab in ("year", "y2025"):
        f = ROOT / f"data/massive/gappers_novol_{lab}.json"
        for r in json.loads(f.read_text()):
            pool[(r["symbol"], r["date"])] = r
    bydate = {}
    for x in legs:
        bydate.setdefault(x["date"], []).append(x)
    tc = C.TapeCost()
    out = []
    miss = 0
    for date in sorted(bydate):
        day = L.load_day(date)
        if day is None:
            miss += len(bydate[date])
            continue
        idx = {s: i for i, s in enumerate(day.syms)}
        for x in bydate[date]:
            i = idx.get(x["symbol"])
            sh = x.get("shares") or 0
            en, ex = x.get("entry") or 0, x.get("exit") or 0
            if i is None or sh <= 0 or en <= 0:
                miss += 1
                continue
            me, mx = _minute(x["entry_time"]), _minute(x["exit_time"])
            if not (0 < me < L.NMIN and 0 < mx < L.NMIN):
                miss += 1
                continue
            cm = (tc.dollars(day, i, me, en, sh)
                  + tc.dollars(day, i, mx, ex, sh))
            cf = (en + ex) * sh * 10.0 / 1e4
            rec = pool.get((x["symbol"], x["date"]))
            out.append(dict(date=date, sym=x["symbol"], pnl=x["pnl"],
                            flat=x["pnl"] - cf, meas=x["pnl"] - cm,
                            cost_meas=cm, cost_flat=cf,
                            gain_full=(rec or {}).get("gain_pct")))
    months = len({r["date"][:7] for r in out})
    g = np.array([r["pnl"] for r in out])
    fl = np.array([r["flat"] for r in out])
    mm = np.array([r["meas"] for r in out])
    gf = np.array([r["gain_full"] if r["gain_full"] is not None else -1
                   for r in out], float)
    cb = np.array([r["cost_meas"] for r in out])
    rep = tc.report()
    print(f"\n{tag}: {len(out)} legs repriced ({miss} could not be "
          f"matched to the panel), {months} months")
    print(f"measured toll: median {rep['median']:.1f} bps/side, "
          f"mean {rep['mean']:.1f}, p90 {rep['p90']:.1f}, "
          f"above 10 bps on {rep['frac_over_10']*100:.0f}% of fills; "
          f"mean ${cb.mean():.2f} a round trip")
    print("\n| oracle veto on the day's FULL-DAY gain | legs | "
          "gross $/tkt | flat10 $/tkt | measured $/tkt | "
          "$/month flat10 | $/month measured |")
    print("|---|---:|---:|---:|---:|---:|---:|")
    for thr in (None, 15, 20, 25, 30, 40, 50):
        m = np.ones(len(g), bool) if thr is None else (gf >= thr)
        if not m.any():
            continue
        lab = "none (the honest champion)" if thr is None \
            else f"keep day-gain >= +{thr}%"
        print(f"| {lab} | {int(m.sum())} | {g[m].mean():+.2f} | "
              f"{fl[m].mean():+.2f} | {mm[m].mean():+.2f} | "
              f"{fl[m].sum()/months:+,.0f} | {mm[m].sum()/months:+,.0f} |")
    (ROOT / "data/massive/cp/reprice.json").write_text(
        json.dumps({"tag": tag, "n": len(out), "months": months,
                    "cost": rep}, indent=1, default=float))
    return out


if __name__ == "__main__":
    a = sys.argv[1:]
    reprice(a[a.index("--tag") + 1] if "--tag" in a else "C37F_hf2")
