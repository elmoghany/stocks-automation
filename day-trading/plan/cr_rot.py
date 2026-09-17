"""COST-REBASE: the ROTATION anchors (C37F-hf2, HOLD1-hf2) under
measured costs.

TWO ROUTES, and the second bounds the error of the first.

  A. LEDGER RE-PRICING (exact for HOLD1, path-frozen for C37F).
     data/massive/rotation_trades_{C37F,HOLD1}_hf2.json carry every leg
     with `entry` (the fill price INCLUDING the incumbent entry slip),
     `exit` (the raw exit price), `shares` and the timestamps. The raw
     fill is recovered as entry/(1+slip_old) and the leg is re-priced

         pnl = (exit*(1-c_out) - fill*(1+c_in)) * shares

     For HOLD1 this is EXACT: trail_pct=999 / stop_pct=99 /
     sell_mode="target_stop_only" means no exit rule can fire, every
     leg is a window-close flatten, and nothing in the engine's path
     depends on the cost. For C37F it freezes the path: its stop and
     trail levels are struck off `entry`, which moves by a few basis
     points, so a leg could in principle stop out a bar earlier. Route
     B measures how much that is worth.

  B. A MATCHED ENGINE SUBSAMPLE. The same configs are run through
     rotation_sim (import-and-wrap, engine flag on) over the FIRST
     `--days` days of each label, twice -- flag off and flag on -- and
     the two per-ticket deltas are compared with route A restricted to
     the same days. Any difference is the path effect.

FIRST FINDING OF THIS FILE, and it changes how every C37* row should
be read: **C37F carries no `slip` at all.** rotation_sim sets
`slippage_bps` only when a config defines `cfg["slip"]`
(rotation_sim.py:1477 and :1512); C37F does not, HOLD1 does (0.001).
Measured straight off the published ledgers by inverting
pnl = (exit*(1-slip) - entry)*shares, the implied per-side exit slip is
**0.000 bps for C37F-hf2 and 10.07 bps for HOLD1-hf2**. So the live
benchmark -- the -$55/ticket row the whole loop is measured against --
is priced with NO transaction cost on either side, not the 10 bps the
EXPERIMENTS-INDEX header claims for every honest number.

Usage:
  python plan/cr_rot.py --reprice
  python plan/cr_rot.py --subsample --days 60
"""
import importlib.util
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT.parent))

import cr_cost as CC                                        # noqa: E402

OUT = HERE / "cr_out"
TRADES = {"C37F": ROOT / "data/massive/rotation_trades_C37F_hf2.json",
          "HOLD1": ROOT / "data/massive/rotation_trades_HOLD1_hf2.json"}
# per-side slip the PUBLISHED hf2 rows were priced at (verified against
# the ledgers themselves by --reprice's `implied_slip_bps`)
LEGACY_SLIP = {"C37F": 0.0, "HOLD1": 10.0}


def implied_slip(t):
    v = []
    for r in t:
        sh, ex = r.get("shares"), r.get("exit")
        if not sh or not ex:
            continue
        v.append(1e4 * (1.0 - (r["pnl"] / sh + r["entry"]) / ex))
    return float(np.median(v)) if v else None


def _t(ts):
    return datetime.fromisoformat(ts).time()


def summarize(legs, label):
    if not legs:
        return {"label": label, "tickets": 0}
    p = np.array([x["pnl"] for x in legs])
    mon = {}
    days = {}
    for x, v in zip(legs, p):
        mon[x["date"][:7]] = mon.get(x["date"][:7], 0.0) + v
        days[x["date"]] = days.get(x["date"], 0.0) + v
    mv = np.array([mon[m] for m in sorted(mon)])
    ds = sorted(days)
    ser = np.array([days[d] for d in ds])
    eq = np.cumsum(ser)
    dd = float(np.min(eq - np.maximum.accumulate(eq))) if eq.size else 0.0
    return {"label": label, "tickets": int(p.size),
            "total": round(float(p.sum()), 0),
            "per_ticket": round(float(p.mean()), 2),
            "per_month": round(float(p.sum()) / max(len(mv), 1), 0),
            "months_pos": f"{int((mv > 0).sum())}/{len(mv)}",
            "traded_days": len(ds),
            "per_day": round(float(p.sum()) / max(len(ds), 1), 2),
            "max_dd": round(dd, 0),
            "best_day": round(float(ser.max()), 0),
            "ex_best_day_total": round(float(p.sum() - ser.max()), 0),
            "mean_c_in_bps": round(float(np.mean(
                [x.get("c_in_bps", 0.0) for x in legs])), 2),
            "mean_c_out_bps": round(float(np.mean(
                [x.get("c_out_bps", 0.0) for x in legs])), 2)}


def reprice(cm, cfg, legs, c_in=None, c_out=None):
    """Re-price a rotation ledger. `c_in`/`c_out` in bps override the
    model (used to reproduce the published row)."""
    slip_old = LEGACY_SLIP[cfg] / 1e4
    out = []
    for r in legs:
        sh = r.get("shares")
        if not sh or not r.get("exit"):
            continue
        fill = r["entry"] / (1.0 + slip_old)
        ci = (c_in if c_in is not None else
              cm.cost_bps(r["symbol"], r["date"], _t(r["entry_time"]),
                          fill * sh))
        co = (c_out if c_out is not None else
              cm.cost_bps(r["symbol"], r["date"], _t(r["exit_time"]),
                          r["exit"] * sh))
        pnl = (r["exit"] * (1 - co / 1e4) - fill * (1 + ci / 1e4)) * sh
        u = dict(r)
        u["pnl"] = float(pnl)
        u["c_in_bps"] = float(ci)
        u["c_out_bps"] = float(co)
        out.append(u)
    return out


def stage_reprice(days=None):
    rep = {"legacy_slip_bps": LEGACY_SLIP, "rows": []}
    for cfg, f in TRADES.items():
        legs = json.loads(f.read_text())
        rep[f"implied_slip_bps_{cfg}"] = round(implied_slip(legs), 3)
        if days:
            keep = sorted({x["date"] for x in legs})[:days]
            legs = [x for x in legs if x["date"] in set(keep)]
        # published row, reproduced from the ledger
        base = reprice(None, cfg, legs, c_in=LEGACY_SLIP[cfg],
                       c_out=LEGACY_SLIP[cfg])
        rep["rows"].append(summarize(base, f"{cfg}-hf2:published"))
        for name, coef in (("measured", CC.IMPACT_COEF),
                           ("spreadonly", 0.0), ("imp03", 0.3),
                           ("imp05", 0.5)):
            cm = CC.CostModel(ext_floor_bps=max(LEGACY_SLIP[cfg], 0.0),
                              impact_coef=coef, enable_impact=coef > 0)
            pr = reprice(cm, cfg, legs)
            s = summarize(pr, f"{cfg}-hf2:{name}")
            s["tier_mix"] = cm.report()
            rep["rows"].append(s)
    OUT.mkdir(exist_ok=True)
    tag = f"_d{days}" if days else ""
    (OUT / f"rot_reprice{tag}.json").write_text(
        json.dumps(rep, indent=1, default=str))
    _print(rep["rows"])
    print(json.dumps({k: v for k, v in rep.items()
                      if k.startswith("implied")}, indent=1))
    return rep


def _print(rows):
    print(f"{'row':>28} {'tkts':>6} {'$/tkt':>9} {'$/mo':>10} {'mo+':>7} "
          f"{'$/day':>8} {'ex-best':>11} {'c_in':>6} {'c_out':>6}")
    for r in rows:
        if not r.get("tickets"):
            continue
        print(f"{r['label'][:28]:>28} {r['tickets']:>6} "
              f"{r['per_ticket']:>9.2f} {r['per_month']:>10,.0f} "
              f"{r['months_pos']:>7} {r['per_day']:>8.2f} "
              f"{r['ex_best_day_total']:>11,.0f} "
              f"{r['mean_c_in_bps']:>6.2f} {r['mean_c_out_bps']:>6.2f}")


def stage_subsample(ndays=60, cfgs=("C37F", "HOLD1")):
    """Run the SAME days twice -- engine flag off, engine flag on --
    and compare to route A on the same days. The difference is the
    path effect of the cost change."""
    import cr_engine as CE
    os.environ.setdefault("ROTSHARD", "crsub")
    RS = _load("rotation_sim", HERE / "rotation_sim.py")
    res = {}
    print(f"--- flag OFF, {ndays} days ---", flush=True)
    res["flat"] = RS.run_many(list(cfgs), ndays)
    ec = CE.EngineCost(cm=CC.CostModel(ext_floor_bps=10.0))
    CE.patch_rotation(RS, ec)
    print(f"--- flag ON (measured), {ndays} days ---", flush=True)
    res["measured"] = RS.run_many(list(cfgs), ndays)
    rep = {"ndays": ndays, "tally": ec.cm.report(), "rows": []}
    for kind in ("flat", "measured"):
        for cid in cfgs:
            for lab in ("year", "y2025"):
                v = res[kind][cid].get(lab)
                if v:
                    rep["rows"].append(dict(cost=kind, cfg=cid, label=lab,
                                            **{k: v[k] for k in
                                               ("total", "days", "tickets",
                                                "pnl_per_ticket")}))
    (OUT / f"rot_subsample_d{ndays}.json").write_text(
        json.dumps(rep, indent=1, default=str))
    print(json.dumps(rep, indent=1, default=str))
    return rep


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


if __name__ == "__main__":
    a = sys.argv[1:]
    d = int(a[a.index("--days") + 1]) if "--days" in a else None
    if "--reprice" in a:
        stage_reprice(d)
    if "--subsample" in a:
        stage_subsample(d or 60)
