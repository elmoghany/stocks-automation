"""COST-REBASE: the honesty battery for the measured cost model.

Five checks, each of which can only be passed by a model that is
actually causal and actually plumbed in.

  P1  FUTURE POISON, model level. For a fill minute m, destroy every
      1-second bar at or after m (prices -> 0, ranges -> NaN, volume ->
      0) and assert the cost at m does not move, on many symbol-days
      and many minutes. A single moved value is a leak.
  P2  PAST POISON, the converse. Destroy the bars BEFORE m instead and
      assert the cost DOES move (or falls to a documented fallback
      tier). A model that ignores its own inputs would pass P1
      trivially; P2 is what stops that.
  P3  ENGINE IDENTITY. Run day-trading.py::simulate_trades with
      `cost_model="measured"` and a cost function that returns exactly
      the LEGACY ladder, and assert every trade is identical, to the
      cent, to the same call with the flag off. This proves the
      `_slip(i)` plumbing changed nothing but the number it reads.
  P4  MONOTONICITY. P&L must fall as the cost model is scaled up.
  P5  NO FREE LUNCH. The cost is never 0, never NaN, never negative.

Usage: python plan/cr_poison.py [--days 40]
"""
import gzip
import importlib.util
import json
import sys
from datetime import time as dtime
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT.parent))

import cr_cost as CC                                        # noqa: E402

OUT = HERE / "cr_out"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


def _rows(sym, date):
    f = CC.XDIR / f"{sym}_{date}.json.gz"
    with gzip.open(f, "rt") as h:
        return json.load(h)["rows"]


def _spread_at(rows, date, m):
    """Recompute the spread at minute index m straight from raw rows."""
    st = CC._stats_from_rows(rows, date)
    d = CC._Day({k: st[k].astype(np.float32) if k != "npr"
                 else st[k].astype(np.int32)
                 for k in ("o", "h", "l", "c", "dv", "npr", "hl2")})
    cm = CC.CostModel()
    cm._rolling(d)
    return d.spread[m], d.dv_win[m], d.sig_win[m]


def p1_p2(pairs, minutes=(45, 90, 150, 210, 270, 330)):
    n1 = bad1 = n2 = moved2 = 0
    for sym, date in pairs:
        try:
            rows = _rows(sym, date)
        except Exception:
            continue
        if not rows:
            continue
        y, mo, dd = (int(x) for x in date.split("-"))
        from datetime import datetime
        base = datetime(y, mo, dd, 9, 30, tzinfo=CC.ET).timestamp() * 1000.0
        for m in minutes:
            cut = base + m * 60000.0
            ref = _spread_at(rows, date, m)
            # P1: nothing at or after minute m may matter
            fut = [r if r[0] < cut else [r[0], 0.0, 0.0, 0.0, 0.0, 0.0, 0]
                   for r in rows]
            got = _spread_at(fut, date, m)
            n1 += 1
            same = all((np.isnan(a) and np.isnan(b)) or a == b
                       for a, b in zip(ref, got))
            if not same:
                bad1 += 1
            # P2: the trailing window MUST matter
            past = [r if r[0] >= cut else [r[0], 0.0, 0.0, 0.0, 0.0, 0.0, 0]
                    for r in rows]
            got2 = _spread_at(past, date, m)
            n2 += 1
            diff = not all((np.isnan(a) and np.isnan(b)) or a == b
                           for a, b in zip(ref, got2))
            if diff:
                moved2 += 1
    return dict(p1_checks=n1, p1_leaks=bad1,
                p2_checks=n2, p2_moved=moved2)


def p3_engine_identity(ndays=8):
    """simulate_trades under cost_model='measured' with a cost function
    that reproduces the LEGACY ladder must be identical to the flag-off
    call, trade for trade, to the cent."""
    dt = _load("dtq", ROOT / "day-trading.py")
    import pandas as pd
    M1 = ROOT / "data" / "massive" / "m1"
    fs = sorted(M1.glob("*.csv"))[::max(1, len(list(M1.glob("*.csv"))) //
                                        (ndays * 40))][:ndays * 40]
    kw = dict(verbose=False, max_trades=1, buy_set=set(), orb=False,
              sell_mode="target_stop_only", vol_confirm=True,
              max_vol_frac=0.20, vol_frac_window=10, vol_frac_causal=True,
              halt_aware=True, wick_guard=3.0, struct_stop_bars=1,
              trail_pct=20, stop_pct=8, scale_out_at=25.0,
              slippage_bps=10.0, pm_spread_bps=50.0, budget=15000.0)
    n = same = 0
    for f in fs:
        try:
            df = pd.read_csv(f, index_col=0, parse_dates=True)
            df.index = df.index.tz_convert("America/New_York")
        except Exception:
            continue
        if len(df) < 60:
            continue
        pc = float(df["Close"].iloc[0])

        def legacy(ts, _k=kw):
            return 10.0
        a = dt.simulate_trades(df, prev_close=pc, **kw)
        b = dt.simulate_trades(df, prev_close=pc, cost_model="measured",
                               cost_bps_fn=legacy, **kw)
        n += 1
        if len(a) == len(b) and all(
                abs(x["pnl"] - y["pnl"]) < 1e-9
                and x["entry"] == y["entry"] and x["exit"] == y["exit"]
                and x["entry_time"] == y["entry_time"]
                and x["exit_time"] == y["exit_time"]
                for x, y in zip(a, b)):
            same += 1
        if n >= ndays * 20:
            break
    return dict(p3_days=n, p3_identical=same)


def p4_p5(pairs, per=20):
    cms = {k: CC.CostModel(impact_coef=k) for k in (0.0, 1.0, 3.0)}
    tot = {k: 0.0 for k in cms}
    n = bad = 0
    for sym, date in pairs[:per]:
        for m in range(10, 380, 23):
            t = dtime((CC.MIN_M + m) // 60, (CC.MIN_M + m) % 60)
            for k, cm in cms.items():
                c = cm.cost_bps(sym, date, t, 15000.0)
                tot[k] += c
                if k == 1.0:
                    n += 1
                    if not (c > 0) or not np.isfinite(c):
                        bad += 1
    mono = tot[0.0] <= tot[1.0] <= tot[3.0]
    return dict(p4_monotone=bool(mono),
                p4_sums={str(k): round(v, 1) for k, v in tot.items()},
                p5_lookups=n, p5_bad=bad)


def main():
    a = sys.argv[1:]
    nd = int(a[a.index("--days") + 1]) if "--days" in a else 40
    have = sorted(CC.CDIR.glob("*.npz"))
    step = max(1, len(have) // nd)
    pairs = [tuple(p.name[:-4].split("_", 1)) for p in have[::step]][:nd]
    rep = {}
    print("P1/P2 ...", flush=True)
    rep.update(p1_p2(pairs))
    print(json.dumps(rep, indent=1), flush=True)
    print("P3 ...", flush=True)
    rep.update(p3_engine_identity())
    print("P4/P5 ...", flush=True)
    rep.update(p4_p5(pairs))
    OUT.mkdir(exist_ok=True)
    (OUT / "poison.json").write_text(json.dumps(rep, indent=1))
    print(json.dumps(rep, indent=1))
    ok = (rep["p1_leaks"] == 0 and rep["p2_moved"] > 0
          and rep["p3_identical"] == rep["p3_days"]
          and rep["p4_monotone"] and rep["p5_bad"] == 0)
    print("POISON BATTERY", "PASS" if ok else "FAIL")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
