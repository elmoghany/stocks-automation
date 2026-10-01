"""LEGACY-6: summarise plan/lm6_out/sim_legs.json (from lm6_sim.py)."""
import json
from pathlib import Path

import numpy as np

ROOT = Path(r"C:\cornell\stocks-automation\day-trading")
D = json.loads((ROOT / "plan/lm6_out/sim_legs.json").read_text())
ND = D["ndays"]
Y2 = "2025-08-01"
NMON = 22


def per(L):
    g = np.array([1e4 * (x["exit"] / x["entry"] - 1) for x in L])
    notl = np.array([x["entry"] * x["shares"] for x in L])
    hs = np.array([x["cost_meas"] / max(x["entry"] * x["shares"], 1e-9) * 1e4 for x in L])
    return g, notl, hs


def summ(L, label, ctrl=None):
    if not L:
        print(f"{label:22s} n=0")
        return {}
    g, notl, hs = per(L)
    n15 = g - 30.0
    nhs = g - hs - 8.0
    y2 = np.array([x["date"] >= Y2 for x in L])
    byday, mon = {}, {}
    for x, v in zip(L, n15):
        byday[x["date"]] = byday.get(x["date"], 0) + v
        mon[x["date"][:7]] = mon.get(x["date"][:7], 0) + v
    tot = n15.sum()
    exbest = tot - max(byday.values())
    ex5 = np.sort(n15)[:-5].sum()
    mpos = sum(v > 0 for v in mon.values())
    s = (f"{label:22s} n={len(L):4d} tkt/d {len(L)/ND:4.2f} gross {g.mean():+7.1f} "
         f"net15 {n15.mean():+7.1f} (Y1 {n15[~y2].mean():+6.1f} / Y2 {n15[y2].mean():+6.1f}) "
         f"netHS {nhs.mean():+7.1f} (Y1 {nhs[~y2].mean():+6.1f} / Y2 {nhs[y2].mean():+6.1f}) "
         f"rtHS {np.median(hs):4.0f}bps-med {hs.mean():4.0f}-mean | $/mo15 {tot/NMON:+6.0f} "
         f"exbestday {exbest/NMON:+6.0f}/mo ex-top5 {ex5/NMON:+6.0f}/mo  mon+ {mpos}/{len(mon)} "
         f"notl-med ${np.median(notl):,.0f}")
    if ctrl:
        cm = np.array(ctrl)
        pct = 100 * np.mean(cm < n15.mean())
        s += f" | ctrl {cm.mean():+6.1f}+-{cm.std():4.1f} pct {pct:3.0f}"
    print(s)
    return dict(n=len(L), net15=n15.mean(), nethS=nhs.mean())


def main():
    L = D["legs"]
    base = [k for k in L if "|" not in k]
    for k in base:
        ctrl = []
        for s in range(10):
            c = L.get(f"{k}|RND{s}") or []
            if c:
                g, _, _ = per(c)
                ctrl.append((g - 30).mean())
        summ(L[k], k, ctrl)
        allc = [x for s in range(10) for x in (L.get(f"{k}|RND{s}") or [])]
        g, _, hs = per(allc)
        print(f"{'':22s} ctrl pooled n={len(allc)} gross {g.mean():+.1f} net15 {g.mean()-30:+.1f} netHS {(g-hs-8).mean():+.1f}")
    # identity check vs saved R4
    old = json.loads((ROOT / "plan/pa_out/cp_r4_legs.json").read_text())["legs"]["R4"]
    a = sum(x["gross"] for x in old)
    b = sum(x["gross"] for x in L["ALL"])
    print(f"\nidentity: saved R4 n={len(old)} gross ${a:,.2f}; re-run ALL n={len(L['ALL'])} gross ${b:,.2f}")


if __name__ == "__main__":
    main()
