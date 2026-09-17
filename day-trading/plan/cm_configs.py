"""CLOSE-MOMENTUM (2026-09-16): the pre-registered configuration sweep.

The four hypotheses of the mandate, expressed as scores over the decision
row table, each run at three exit bars (15:50 / 15:55 / 15:59) and at
topk in {1, 3, 7}, with the inverted signal run as a matched mirror for
every one of them.

  H1  market intraday momentum, single-name form: the FIRST half-hour
      return predicts the LAST half-hour return.        score = r_first
  H1x cross-sectional form: buy the names whose own first half-hour was
      strongest (or weakest) at 15:30.                  score = xs_rank_first
  H1m market-timing form: trade only when the halal universe's
      equal-weight session return is positive.          gate = breadth > 0
  H2  late-session continuation on causal intraday state:
      ret_open / dist_vwap / rvol / breadth at 15:00-15:30.
  H3  the 12:00-13:00 window (WIDE-NET's ranked next idea).
  H4  the combination: r_first + r_mid, market-demeaned, top-k at 15:30.

Nothing here is fitted. The one fitted arm lives in plan/cm_model.py and
is trained on Y1 only.

Usage:  python plan/cm_configs.py [--universe wide|gap] [--quick]
Writes: data/massive/cm/configs_{universe}.json
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "rl2"))
import cm_lib as L                                            # noqa: E402
import cm_single as S                                         # noqa: E402

LAST_EXITS = ["15:50", "15:55", "15:59"]


def specs(t):
    """(name, score, decisions, exits, topk_list, gate) tuples."""
    f = t.f
    out = []

    def add(name, sc, decs, exits, topks=(1, 3, 7), gate=None):
        out.append(dict(name=name, score=sc, decs=decs, exits=list(exits),
                        topks=list(topks), gate=gate))

    # ---- H1 single-name first-half-hour -> last-half-hour
    add("H1-first", f("r_first"), ["15:30"], LAST_EXITS)
    add("H1-first-INV", -f("r_first"), ["15:30"], LAST_EXITS)
    add("H1-mid", f("r_mid"), ["15:30"], LAST_EXITS)
    add("H1-mid-INV", -f("r_mid"), ["15:30"], LAST_EXITS)
    add("H1-sum", f("r_first") + f("r_mid"), ["15:30"], LAST_EXITS)
    add("H1-sum-INV", -(f("r_first") + f("r_mid")), ["15:30"], LAST_EXITS)

    # ---- H1x cross-sectional ranks (market-demeaned = the same ordering)
    add("H1x-rank-first", f("xs_rank_first"), ["15:30"], LAST_EXITS)
    add("H1x-rank-first-INV", -f("xs_rank_first"), ["15:30"], LAST_EXITS)
    add("H1x-rank-mid", f("xs_rank_mid"), ["15:30"], LAST_EXITS)
    add("H1x-rank-mid-INV", -f("xs_rank_mid"), ["15:30"], LAST_EXITS)

    # ---- H1m market timing: only on days the halal universe is green
    add("H1m-breadth+", f("r_first"), ["15:30"], LAST_EXITS,
        gate=f("breadth") > 0)
    add("H1m-breadth-", f("r_first"), ["15:30"], LAST_EXITS,
        gate=f("breadth") < 0)
    add("H1m-flat-breadth+", np.zeros(len(t.px_in)), ["15:30"], LAST_EXITS,
        gate=f("breadth") > 0)

    # ---- H1v the published conditioning: only on high-volatility days
    sig = f("sigma30")
    hi = sig >= np.nanpercentile(sig[t.split == 0], 70)
    add("H1v-hivol", f("r_first"), ["15:30"], LAST_EXITS, gate=hi)
    add("H1v-hivol-mid", f("r_mid"), ["15:30"], LAST_EXITS, gate=hi)
    rv = f("rvol")
    hrv = rv >= np.nanpercentile(rv[t.split == 0], 70)
    add("H1v-hirvol", f("r_first"), ["15:30"], LAST_EXITS, gate=hrv)
    add("H1v-hirvol-mid", f("r_mid"), ["15:30"], LAST_EXITS, gate=hrv)

    # ---- H2 late-session continuation on causal intraday state
    for dec in ("15:00", "15:15", "15:30"):
        add(f"H2-retopen@{dec}", f("ret_open"), [dec], LAST_EXITS)
        add(f"H2-retopen-INV@{dec}", -f("ret_open"), [dec], LAST_EXITS)
        add(f"H2-vwap@{dec}", f("dist_vwap"), [dec], LAST_EXITS)
        add(f"H2-vwap-INV@{dec}", -f("dist_vwap"), [dec], LAST_EXITS)
        add(f"H2-rvol@{dec}", f("rvol"), [dec], LAST_EXITS)
        add(f"H2-disthi@{dec}", f("dist_hi"), [dec], LAST_EXITS)
        add(f"H2-disthi-INV@{dec}", -f("dist_hi"), [dec], LAST_EXITS)
        add(f"H2-flat@{dec}", np.zeros(len(t.px_in)), [dec], LAST_EXITS)

    # ---- H3 the noon window
    for ex in ("13:00", "14:00", "15:59"):
        add(f"H3-flat@12:00->{ex}", np.zeros(len(t.px_in)), ["12:00"], [ex])
        add(f"H3-retopen@12:00->{ex}", f("ret_open"), ["12:00"], [ex])
        add(f"H3-retopen-INV@12:00->{ex}", -f("ret_open"), ["12:00"], [ex])
        add(f"H3-first@12:00->{ex}", f("r_first"), ["12:00"], [ex])
        add(f"H3-vwap@12:00->{ex}", f("dist_vwap"), ["12:00"], [ex])
        add(f"H3-vwap-INV@12:00->{ex}", -f("dist_vwap"), ["12:00"], [ex])
        add(f"H3-rvol@12:00->{ex}", f("rvol"), ["12:00"], [ex])
    for ex in ("14:00", "15:59"):
        add(f"H3-flat@13:00->{ex}", np.zeros(len(t.px_in)), ["13:00"], [ex])
        add(f"H3-retopen@13:00->{ex}", f("ret_open"), ["13:00"], [ex])
        add(f"H3-rvol@13:00->{ex}", f("rvol"), ["13:00"], [ex])
        add(f"H3-vwap@13:00->{ex}", f("dist_vwap"), ["13:00"], [ex])

    # ---- H4 combined, market-demeaned cross-section at 15:30
    add("H4-dm-sum", f("r_first_dm") + f("r_mid_dm"), ["15:30"], LAST_EXITS)
    add("H4-dm-sum-INV", -(f("r_first_dm") + f("r_mid_dm")), ["15:30"],
        LAST_EXITS)
    add("H4-dm-first", f("r_first_dm"), ["15:30"], LAST_EXITS)
    add("H4-dm-first-INV", -f("r_first_dm"), ["15:30"], LAST_EXITS)
    # the pure "buy everything at 15:30" reference
    add("H4-flat@15:30", np.zeros(len(t.px_in)), ["15:30"], LAST_EXITS)
    add("H4-flat@15:45", np.zeros(len(t.px_in)), ["15:45"], ["15:50", "15:55",
                                                             "15:59"])
    return out


def main():
    uni = sys.argv[sys.argv.index("--universe") + 1] \
        if "--universe" in sys.argv else "wide"
    t = S.Table(uni)
    print(f"{uni}: {len(t.px_in):,} rows, {len(t.dates)} dates", flush=True)
    res = {}
    sp = specs(t)
    n = sum(len(s["exits"]) * len(s["topks"]) for s in sp)
    print(f"{len(sp)} specs -> {n} rows", flush=True)
    done = 0
    for s in sp:
        for ex in s["exits"]:
            for k in s["topks"]:
                tr = S.run(t, s["score"], ex, s["decs"], topk=k,
                           eligible=s["gate"])
                nm = f"{s['name']}|{ex}|k{k}"
                res[nm] = S.row(t, tr, nm)
                done += 1
        print(f"  [{done}/{n}] {s['name']}", flush=True)
    L.write_json(f"configs_{uni}.json", res)

    rows = sorted(res.items(), key=lambda kv: -kv[1]["all"]["per_ticket"])
    print(f"\n== top 25 by $/ticket ({uni}) ==")
    hdr = (f"{'config':38s} {'n':>5s} {'$/tkt':>8s} {'$/mo':>9s} "
           f"{'y1':>8s} {'y2':>8s} {'aug':>7s} {'exbest':>10s}")
    print(hdr)
    for nm, v in rows[:25]:
        a = v["all"]
        print(f"{nm:38s} {a['tickets']:5d} {a['per_ticket']:+8.2f} "
              f"{a['per_month']:+9.1f} {v['y1']['per_ticket']:+8.2f} "
              f"{v['y2']['per_ticket']:+8.2f} "
              f"{v['aug2026']['per_ticket']:+7.2f} "
              f"{a['ex_best_total']:+10.0f}")
    print(f"\nmedian $/ticket over {len(rows)} configs: "
          f"{np.median([v['all']['per_ticket'] for _, v in rows]):+.2f}")
    print("wrote", L.OUT / f"configs_{uni}.json", flush=True)


if __name__ == "__main__":
    main()
