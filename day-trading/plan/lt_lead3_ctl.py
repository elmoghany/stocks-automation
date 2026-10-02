"""LEADS-TEST lead 3 audit: sanity-guarded market cap, SPY-excess returns,
and a 30-seed random large-cap control on the 12 whole-market census dates.

Guards (data-error guards, motivated by the broken-mcap records, not by
outcomes): prev close >= $5; dvol60 / mcap >= 0.0005 (a $2B company trades
>= $1M/day); mcap <= $5T.
Control: for each census event (date D, entry minute em) draw a random
whole-market name on D with the same classification (split-safe mcap >= $2B,
dvol60 >= $5M, guards) that did NOT print a premarket +10% close, buy the
OPEN of its first print at/after em, sell the OPEN of its first print at/after
10:00. 30 seeds; percentile of the lead's census total among seed totals.
    python plan/lt_lead3_ctl.py
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lt_lib as LL                                         # noqa: E402
import lt_lead3 as X                                        # noqa: E402
import cp_premkt as PM                                      # noqa: E402
import cp_prior as PR                                       # noqa: E402
import cp_lib as L                                          # noqa: E402

ROOT = LL.ROOT
EV = json.loads((ROOT / "data/research_oct/lt_lead3_events.json").read_text())
for e in EV:
    e["mcap"], e["mcap_ok"], e["sh_src"] = X.mcap_check(e["sym"], e["date"], e["pc"])


def guard(e):
    return (e["pc"] >= 5 and e["mcap"] is not None and e["mcap"] <= 5e12
            and e["dv60"] / e["mcap"] >= 5e-4)


def sel(e, src=None):
    return (not e["early"]) and e["pool_ok"] and e.get("em") is not None and \
        e.get("x1000") is not None and e["mcap_ok"] == "ok" and e["mcap"] >= 2e9 and \
        e["dv60"] >= 5e6 and guard(e) and (src is None or e["sh_src"] == src)


def spy_ret(date, em):
    b = PM.read_bars("SPY", date)
    if b is None:
        f = ROOT / f"data/massive/m1etf/SPY_{date}.csv"
        if not f.exists():
            return None
        return None
    o, h, l, c, v = b
    a = X.first_print(c, em)
    z = X.first_print(c, X.M1000)
    if a is None or z is None:
        return None
    return o[z] / o[a] - 1


def spy_bars(date):
    import p3_lib as PL
    for d in ("m1etf", "m1c", "m1"):
        f = ROOT / f"data/massive/{d}/SPY_{date}.csv"
        if f.exists():
            r = PL.read_bars_csv(f, date)
            if r is not None:
                return r
    return None


def main():
    rows = [e for e in EV if sel(e)]
    nd = {sp: sum(1 for d in L.panel_dates() if LL.split_of(d) == sp) for sp in ("Y1", "Y2", "OOS")}
    nd["ALL"] = sum(nd.values())
    print(f"guarded panel+census events: {len(rows)} (pit {sum(e['sh_src']=='pit' for e in rows)}, "
          f"present-scaled {sum(e['sh_src']=='present-scaled' for e in rows)})")
    # SPY excess
    cache = {}
    exc = []
    for e in rows:
        if e["date"] not in cache:
            cache[e["date"]] = spy_bars(e["date"])
        b = cache[e["date"]]
        if b is None:
            continue
        o, h, l, c, v = b
        a = X.first_print(c, e["em"])
        z = X.first_print(c, X.M1000)
        if a is None or z is None:
            continue
        exc.append((e, e["x1000"] - (o[z] / o[a] - 1)))
    print(f"SPY bars for {len(exc)}/{len(rows)} events")
    for sp in ("Y1", "Y2", "OOS", "ALL"):
        r = [1e4 * e["x1000"] for e, x in exc if sp == "ALL" or LL.split_of(e["date"]) == sp]
        x = [1e4 * x for e, x in exc if sp == "ALL" or LL.split_of(e["date"]) == sp]
        if r:
            print(f"  {sp}: n {len(r)} raw gross {np.mean(r):+.1f}  SPY-excess gross {np.mean(x):+.1f} "
                  f"(t {np.mean(x)/(np.std(x,ddof=1)/np.sqrt(len(x))):+.2f})")
    # main line, guarded, by source
    import lt_lead3_report as R
    for src, lab in ((None, "guarded, any shares source"), ("pit", "guarded, PIT shares only"),
                     ("present-scaled", "guarded, present-scaled only")):
        rr = [e for e in EV if sel(e, src)]
        print(f"\n### PANEL+census {lab} -> 10:00 (n={len(rr)})")
        R.hdr()
        R.line(lab, rr, nd, "x1000")
        rr2 = [e for e in rr if e["half"] <= 10]
        print(f"#### + spread <= 10 (n={len(rr2)})")
        R.line(lab + " +spread", rr2, nd, "x1000")
        rr3 = [e for e in rr2 if np.isfinite(e["sig"]) and e["sig"] <= 0.017]
        print(f"#### + sigma1 <= 0.017 (full stack, n={len(rr3)})")
        R.line(lab + " full stack", rr3, nd, "x1000")
        R.line(lab + " full stack, stack exits", rr3, nd, "xstack")
    # census random control
    cen = [e for e in EV if e["census"] and sel(e)]
    print(f"\ncensus guarded events: {len(cen)}  -> " + ", ".join(f"{e['date']} {e['sym']} {1e4*e['x1000']:+.0f}" for e in cen))
    pool = {}
    crossers = {(e["date"], e["sym"]) for e in EV}
    for d in sorted({e["date"] for e in cen}):
        pr = PR.load(d)
        cand = []
        for s, p in pr.items():
            if (d, s) in crossers or not X.TICK_OK(s):
                continue
            dv = p.get("dvol60") or 0
            pc = p.get("prevclose") or 0
            if dv < 5e6 or pc < 5:
                continue
            m, ok, src = X.mcap_check(s, d, pc)
            if ok != "ok" or m is None or m < 2e9 or m > 5e12 or dv / m < 5e-4:
                continue
            cand.append(s)
        pool[d] = sorted(cand)
        print(f"  {d}: {len(cand)} random-control candidates")
    bars_cache = {}

    def rb(s, d):
        k = (s, d)
        if k not in bars_cache:
            bars_cache[k] = PM.read_bars(s, d)
        return bars_cache[k]
    tots = []
    lead_tot = sum(1e4 * e["x1000"] for e in cen)
    rng = np.random.default_rng(11)
    for seed in range(30):
        t = 0.0
        for e in cen:
            for _ in range(20):
                s = pool[e["date"]][rng.integers(len(pool[e["date"]]))]
                b = rb(s, e["date"])
                if b is None:
                    continue
                o, h, l, c, v = b
                a = X.first_print(c, e["em"], X.M1000 - 1)
                z = X.first_print(c, X.M1000)
                if a is None or z is None:
                    continue
                t += 1e4 * (o[z] / o[a] - 1)
                break
        tots.append(t)
    tots = np.array(tots)
    print(f"census lead total gross {lead_tot:+.0f} on {len(cen)} trades; random large-cap control "
          f"mean {tots.mean():+.0f} sd {tots.std():.0f}; percentile "
          f"{100*np.mean(tots < lead_tot):.0f}")


if __name__ == "__main__":
    main()
