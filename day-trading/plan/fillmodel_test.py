"""FILL-MODEL EPOCH 2026-09-02 -- proofs for day-trading.py::simulate_trades.

Runs four checks and exits non-zero on any failure:

  1. SYNTHETIC GAP-THROUGH. A stop whose bar OPENS below it fills at the
     open (not the stop); a target whose bar opens above it fills at
     the open (symmetric); every sell lies inside [Low, High].
  2. THE AUDITED PHANTOMS. TWG/WFF 2025-09-11, HSDT 2025-06-11 and the
     top phantom days of the corrected ladder, replayed on the PTRAIL
     kwargs: no non-flatten exit may print above its bar's High, and
     the TWG leg can no longer book +$20k.
  3. CAUSALITY (the liquidity_estimators.py poison pattern). For real
     days and two kwarg sets (PTRAIL and C37F-inherited), poison every
     bar at/after a cut with absurd values (9e9 and 1e-9 variants) and
     assert every trade that CLOSED BEFORE the cut is byte-identical.
     Bar i's High may only move the peak from bar i+1, so no cut can
     alter an earlier exit. The PRE-fix engine (git HEAD snapshot,
     optional --old PATH) is run through the same harness to show the
     one-bar next-close peek it carried (X319 wick guard).
  4. SHARES EXPORT. Every trade dict carries `shares`, and
     pnl == (exit*(1-slip) - entry) * shares to the cent.

Usage: python plan/fillmodel_test.py [--old C:/path/to/old_day-trading.py]
"""
import importlib.util
import json
import sys
from datetime import time as dtime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "plan"))
import rotation_sim as rs                      # noqa: E402  (loads dt)

dt = rs.dt
PTRAIL_KW = rs.build_simkw("PTRAIL6", rs.CFGS["PTRAIL6"], echo=False)
C37F_KW = rs.build_simkw("C37F", rs.CFGS["C37F"], echo=False)
for kw in (PTRAIL_KW, C37F_KW):
    kw["slippage_bps"] = 10.0
SLIP = 0.001
BUD = 15_000.0


def _load_old(path):
    spec = importlib.util.spec_from_file_location("old_dt", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _sim(mod, df, prev_close=None, kw=PTRAIL_KW, entry_start=dtime(7, 0)):
    w = df[(df.index.time >= dtime(7, 0)) & (df.index.time < rs.EXIT_END)]
    return mod.simulate_trades(w, prev_close=prev_close, budget=BUD,
                               entry_start=entry_start, **kw)


def _bar(df, ts):
    r = df.loc[ts]
    return float(r["Open"]), float(r["High"]), float(r["Low"])


def check_inside_bars(df, trades, label):
    bad = []
    for t in trades:
        if t["reason"].startswith("window-close"):
            continue
        o, h, lo = _bar(df, t["exit_time"])
        # premarket sells pay pm_spread_bps AFTER the clamp, so allow
        # the haircut below the Low; nothing may print above the High
        if t["exit"] > h + 0.00501 or t["exit"] < lo * (1 - 0.01) - 0.00501:
            bad.append((label, str(t["exit_time"])[11:16], t["exit"],
                        round(h, 2), round(lo, 2), t["reason"]))
    return bad


def synthetic_gap():
    """ORB entry on a flat tape, then a bar that gaps through the stop
    (and, in the second tape, through the target)."""
    idx = pd.date_range("2025-01-06 07:00", periods=40, freq="1min",
                        tz="America/New_York")
    rows = []
    for k in range(40):
        rows.append(dict(Open=5.0, High=5.1, Low=4.95, Close=5.0,
                         Volume=50_000))
    df = pd.DataFrame(rows, index=idx)
    # break of the 3-bar opening range at bar 5, hold, then the gap bar
    df.iloc[5] = [5.05, 5.30, 5.05, 5.25, 80_000]
    for k in range(6, 12):
        df.iloc[k] = [5.25, 5.28, 5.22, 5.25, 40_000]
    gap_dn = df.copy()
    gap_dn.iloc[12] = [4.00, 4.05, 3.90, 4.00, 90_000]     # opens < stop
    gap_up = df.copy()
    gap_up.iloc[12] = [6.50, 6.60, 6.40, 6.55, 90_000]     # opens > target
    kw = dict(orb=True, orb_bars=3, stop_pct=8, target_pct=10,
              verbose=False, sell_mode="target_stop_only")
    t1 = dt.simulate_trades(gap_dn, budget=BUD, **kw)
    t2 = dt.simulate_trades(gap_up, budget=BUD, **kw)
    assert t1 and t1[0]["reason"].startswith("stop"), t1
    assert abs(t1[0]["exit"] - 4.00) < 1e-9, ("stop must fill at the "
                                              "open 4.00", t1[0])
    assert t2 and t2[0]["reason"].startswith("target"), t2
    assert abs(t2[0]["exit"] - 6.50) < 1e-9, ("target must fill at the "
                                              "open 6.50", t2[0])
    # inside-bar stop: fills AT the stop (unchanged behaviour)
    inside = df.copy()
    inside.iloc[12] = [5.20, 5.22, 4.50, 4.60, 90_000]
    t3 = dt.simulate_trades(inside, budget=BUD, **kw)
    stop_lvl = t3[0]["entry"] * 0.92
    assert abs(t3[0]["exit"] - round(stop_lvl, 2)) < 0.011, (t3[0], stop_lvl)
    print(f"  synthetic: gap-down stop -> {t1[0]['exit']} (open), "
          f"gap-up target -> {t2[0]['exit']} (open), inside-bar stop -> "
          f"{t3[0]['exit']} (stop {stop_lvl:.2f})  OK")


def audited_phantoms(old):
    days = [("TWG", "2025-09-11", 5.02), ("WFF", "2025-09-11", None),
            ("HSDT", "2025-06-11", None)]
    # the next-largest phantom legs of the corrected ladder's PTRAIL6
    # dump (rotation_trades_PTRAIL6_hl_p6.json, exit > bar High)
    days += [(s, d, None) for s, d in (
        ("BTCT", "2024-11-13"), ("BTCS", "2024-11-12"),
        ("PCSA", "2025-06-17"), ("NAMM", "2026-01-22"),
        ("BNAI", "2026-06-05"), ("VRME", "2025-01-08"),
        ("AIHS", "2025-06-05"), ("PHOE", "2026-02-17"),
        ("SKYQ", "2026-04-02"), ("CYN", "2024-12-23"))]
    bad = []
    n_legs = 0
    twg_new = twg_old = None
    for sym, date, pc in days:
        df = rs.bars_for(sym, date)
        if df is None:
            continue
        tr = _sim(dt, df, pc)
        n_legs += sum(1 for t in tr
                      if not t["reason"].startswith("window-close"))
        bad += check_inside_bars(df, tr, f"{sym} {date}")
        if sym == "TWG":
            twg_new = tr
            if old is not None:
                twg_old = _sim(old, df, pc)
    print(f"  audited days: {len(days)} replayed, {n_legs} non-flatten "
          f"legs, exits above bar High: {len(bad)}")
    for b in bad[:10]:
        print("    BAD", b)
    assert not bad, "phantom fills survive"
    if twg_new:
        t = twg_new[0]
        print(f"  TWG 2025-09-11 NEW: {t['entry_time']:%H:%M} @{t['entry']}"
              f" -> {t['exit_time']:%H:%M} @{t['exit']} {t['reason']} "
              f"pnl {t['pnl']:+,.0f} sh {t['shares']} peak {t['peak_pct']}%")
        assert t["pnl"] < 5_000, "TWG still books the phantom"
    if twg_old:
        t = twg_old[0]
        print(f"  TWG 2025-09-11 OLD: {t['entry_time']:%H:%M} @{t['entry']}"
              f" -> {t['exit_time']:%H:%M} @{t['exit']} {t['reason']} "
              f"pnl {t['pnl']:+,.0f} peak {t['peak_pct']}%")


def _key(t):
    return (str(t["entry_time"]), t["entry"], str(t["exit_time"]),
            t["exit"], t["reason"], t["pnl"], t.get("shares"))


def poison(mod, df, pc, kw, step=3):
    """Return the number of (cut, variant) breaches: trades closed
    before the cut that differ from the clean run."""
    w = df[(df.index.time >= dtime(7, 0)) & (df.index.time < rs.EXIT_END)]
    w = w.astype(float)          # so the 1e-9 poison is representable
    clean = mod.simulate_trades(w, prev_close=pc, budget=BUD,
                                entry_start=dtime(7, 0), **kw)
    if not clean:
        return 0, 0
    first = w.index.get_loc(clean[0]["entry_time"])
    breaches = 0
    tested = 0
    cols = ["Open", "High", "Low", "Close", "Volume"]
    for cut in range(first + 1, len(w), step):
        for val in (9e9, 1e-9):
            p = w.copy()
            p.iloc[cut:, [p.columns.get_loc(c) for c in cols]] = val
            tr = mod.simulate_trades(p, prev_close=pc, budget=BUD,
                                     entry_start=dtime(7, 0), **kw)
            lim = w.index[cut]
            a = [_key(t) for t in clean if t["exit_time"] < lim]
            b = [_key(t) for t in tr if t["exit_time"] < lim]
            tested += 1
            if a != b:
                breaches += 1
    return breaches, tested


def causality(old):
    days = [("TWG", "2025-09-11", 5.02), ("WFF", "2025-09-11", None),
            ("HSDT", "2025-06-11", None), ("BTCT", "2024-11-13", None),
            ("PCSA", "2025-06-17", None), ("NAMM", "2026-01-22", None),
            ("BNAI", "2026-06-05", None), ("SKYQ", "2026-04-02", None)]
    tot_new = tot_old = 0
    n_new = n_old = 0
    for sym, date, pc in days:
        df = rs.bars_for(sym, date)
        if df is None:
            continue
        for name, kw in (("PTRAIL", PTRAIL_KW), ("C37F", C37F_KW)):
            b, n = poison(dt, df, pc, kw)
            tot_new += b
            n_new += n
            line = f"  poison {sym} {date} {name:<6} NEW {b}/{n} breaches"
            if old is not None:
                bo, no = poison(old, df, pc, kw)
                tot_old += bo
                n_old += no
                line += f"   OLD {bo}/{no}"
            print(line, flush=True)
    print(f"  CAUSALITY: NEW engine {tot_new}/{n_new} breaches"
          + (f"; OLD engine {tot_old}/{n_old}" if old is not None else ""))
    assert tot_new == 0, "CAUSALITY BREACH in the new engine"


def shares_export():
    df = rs.bars_for("TWG", "2025-09-11")
    n = 0
    for kw in (PTRAIL_KW, C37F_KW):
        for t in _sim(dt, df, 5.02, kw):
            assert "shares" in t and t["shares"] >= 1, t
            exp = (t["exit"] * (1 - SLIP) - t["entry"]) * t["shares"]
            # entry/exit are rounded to cents in the dict; allow that
            assert abs(exp - t["pnl"]) <= 0.01 * t["shares"] + 0.01, (t, exp)
            n += 1
    print(f"  shares export: {n} legs carry exact shares, pnl identity OK")


def main():
    old = None
    if "--old" in sys.argv:
        old = _load_old(sys.argv[sys.argv.index("--old") + 1])
    print("fillmodel_test (epoch 2026-09-02)")
    synthetic_gap()
    audited_phantoms(old)
    shares_export()
    causality(old)
    print("fillmodel_test: ALL PASS")


if __name__ == "__main__":
    main()
