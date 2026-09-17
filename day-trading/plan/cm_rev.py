"""CLOSE-MOMENTUM (2026-09-16): the late-session REVERSAL composite --
the closest thing to a signal this line found, tested the honest way.

WHY THIS EXISTS. The mandate's hypothesis 1 is momentum: the first and
the second-to-last half-hour returns should PREDICT the last half-hour
return with a positive sign. On this universe every rank IC that clears
0.02 in the last hour has the OPPOSITE sign, and the strongest of them
is stable across both splits:

  decision 15:00, exit 15:59      r_mid (the 14:30->15:00 return)  -0.045
                                  dist_vwap30                      -0.042
                                  dist_hi                          -0.028
  decision 15:30, exit 15:59      dist_hi                          -0.036
                                  ret_open                         -0.032
                                  dist_vwap                        -0.029

So the late session on the halal wide universe mean-REVERTS: what has
sagged furthest below its own 30-minute VWAP and its own session high is
what drifts back into the close.

THE PROTOCOL, so this is not a sixth look at the same data.
  * The SIGN and the MEMBER LIST of the composite are chosen on Y1
    (2024-10-22..2025-07-31) alone, by the Y1 column of the IC table and
    nothing else. A feature is in the composite iff |IC_y1| >= 0.02.
  * The weights are fixed at 1 -- a within-day cross-sectional z-score of
    each member, summed, times the Y1 sign. No coefficient is fitted, so
    there is nothing for the Y2 data to have chosen.
  * Y2 (2025-08-01..2026-07-31) and the aug-2026 stub are then read ONCE
    per exit bar, with the full control battery.

Usage:  python plan/cm_rev.py [--universe wide]
Writes: data/massive/cm/rev_{universe}.json
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "rl2"))
import cm_lib as L                                            # noqa: E402
import cm_controls as CT                                      # noqa: E402
import cm_model as M                                          # noqa: E402
import cm_single as S                                         # noqa: E402

IC_MIN = 0.02
PAIRS = [("15:00", "15:59"), ("15:30", "15:59"), ("15:15", "15:59"),
         ("15:00", "15:55"), ("15:30", "15:55"), ("15:00", "15:50"),
         ("15:30", "15:50")]


def zscore_within_day(t, x, mask):
    """Cross-sectional z-score inside each (date, decision) group -- the
    only normalisation a decision at time m can actually compute."""
    out = np.zeros_like(x, dtype=np.float64)
    key = t.date_i.astype(np.int64) * 64 + t.dec_i
    o = np.argsort(key, kind="stable")
    k = key[o]
    starts = np.flatnonzero(np.r_[True, k[1:] != k[:-1]])
    ends = np.r_[starts[1:], len(k)]
    for s, e in zip(starts, ends):
        rows = o[s:e]
        rows = rows[mask[rows]]
        if rows.size < 3:
            continue
        v = x[rows].astype(np.float64)
        sd = v.std()
        out[rows] = (v - v.mean()) / sd if sd > 0 else 0.0
    return out


def build(t, dec, exit_lab):
    """(score, members) with the sign and membership taken from Y1 only."""
    m = M.eligible(t, dec, exit_lab)
    y = M.net_ret(t, dec, exit_lab)
    y1 = m & (t.split == 0)
    members = []
    for f in t.feat:
        ic = M.spearman(t.f(f)[y1], y[y1])
        if np.isfinite(ic) and abs(ic) >= IC_MIN:
            members.append((f, float(np.sign(ic)), round(float(ic), 4)))
    if not members:
        return None, []
    sc = np.zeros(len(t.px_in))
    for f, sgn, _ in members:
        sc += sgn * zscore_within_day(t, t.f(f), m)
    sc = np.where(m, sc, -np.inf)
    return sc, members


def stage_cost(t):
    """What the TOLL is worth, and whether removing it would be enough.

    The same Y1-selected composite priced at 10 (incumbent), 5, 2 and 0 bps a
    side. UNIVERSE+QUOTES measured the real inside spread on this universe at
    2-6 bps (half-spread 1-3), so the incumbent ladder is 2-5x conservative;
    this turns the consequence into a number instead of an argument -- and the
    0 bps row is the frictionless ceiling, the honest upper bound on anything
    this line could ever earn.
    """
    out = {}
    base = L.FEE_BPS
    for dec, ex in (("15:00", "15:59"), ("15:30", "15:59")):
        sc, _ = build(t, dec, ex)
        if sc is None:
            continue
        for k in (1, 7):
            rows = {}
            for fee in (10.0, 5.0, 2.0, 0.0):
                L.FEE_BPS = fee
                r = L.split_rows(S.run(t, sc, ex, [dec], topk=k), t.dates, "")
                rows[f"{fee:g}bps"] = {
                    "tickets": r["all"]["tickets"],
                    "per_ticket": r["all"]["per_ticket"],
                    "per_month": r["all"]["per_month"],
                    "y1": r["y1"]["per_ticket"], "y2": r["y2"]["per_ticket"]}
            L.FEE_BPS = base
            out[f"REV|{dec}->{ex}|k{k}"] = rows
    rows = {}
    for fee in (10.0, 0.0):
        L.FEE_BPS = fee
        pt = [L.summarize(S.run(t, np.random.default_rng(90_000 + s)
                                .random(len(t.px_in)), "15:59", ["15:30"],
                                topk=7), len(t.dates), "")["per_ticket"]
              for s in range(8)]
        rows[f"{fee:g}bps"] = {"per_ticket": round(float(np.mean(pt)), 2)}
    L.FEE_BPS = base
    out["RANDOM|15:30->15:59|k7"] = rows
    return out


def main():
    uni = sys.argv[sys.argv.index("--universe") + 1] \
        if "--universe" in sys.argv else "wide"
    t = S.Table(uni)
    if "--stage" in sys.argv and \
            sys.argv[sys.argv.index("--stage") + 1] == "cost":
        c = stage_cost(t)
        L.write_json(f"rev_cost_{uni}.json", c)
        print(json.dumps(c, indent=1))
        return
    res = {}
    for dec, ex in PAIRS:
        sc, members = build(t, dec, ex)
        if sc is None:
            print(f"{dec}->{ex}: no member clears |IC_y1| >= {IC_MIN}")
            continue
        key = f"{dec}->{ex}"
        res[key] = {"members": members}
        print(f"\n== {key}  composite of {len(members)} Y1-selected features ==")
        for f, sgn, ic in members:
            print(f"   {'+' if sgn > 0 else '-'}{f:18s} IC_y1 {ic:+.4f}")
        for k in (1, 3, 7):
            r = CT.one(t, f"REV|{key}|k{k}", sc, [dec], ex, k)
            res[key][f"k{k}"] = r
            a = r["row"]["all"]
            print(f"   k{k}: ALL n={a['tickets']:5d} ${a['per_ticket']:+7.2f}"
                  f"/tkt ${a['per_month']:+8.1f}/mo | "
                  f"Y1 ${r['row']['y1']['per_ticket']:+7.2f} "
                  f"Y2 ${r['row']['y2']['per_ticket']:+7.2f} "
                  f"aug ${r['row']['aug2026']['per_ticket']:+7.2f} | "
                  f"rand ${r['random']['mean_per_ticket']:+6.2f} "
                  f"pct {r['pctile_total']:5.1f}/{r['pctile_ex_best']:5.1f} | "
                  f"inv ${r['inverted']['per_ticket']:+6.2f} "
                  f"shuf ${r['shuffled']['mean_per_ticket']:+6.2f} | "
                  f"t={r['bootstrap'].get('daily_t', 0):+5.2f} "
                  f"p5 ${r['bootstrap'].get('per_month_p5', 0):+8.1f}",
                  flush=True)
    L.write_json(f"rev_{uni}.json", res)
    print("\nwrote", L.OUT / f"rev_{uni}.json", flush=True)


if __name__ == "__main__":
    main()
