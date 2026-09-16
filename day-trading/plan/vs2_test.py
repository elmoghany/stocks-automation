"""VS2-SERIES PROOFS (2026-09-16) -- the video-sourced entry triggers.

Three checks, non-zero exit on any failure:

  1. IDENTITY. With every VS2 kwarg at its default the engine must be
     byte-identical to the pre-edit copy. Run the champion (C37F) and
     PTRAIL kwarg sets over real symbol-days through BOTH modules and
     compare the trade dicts field for field. `--old PATH` points at the
     snapshot taken before the edit.
  2. SMOKE. Each new trigger is run on real days and its trades printed,
     so a trigger that never fires (or fires on every bar) is visible
     rather than silently producing an empty table.
  3. POISON (the fillmodel_test.py / liquidity_estimators.py pattern).
     For every VS2 kwarg set, replace all bars at/after a cut with
     absurd values (9e9 and 1e-9) and assert every trade that CLOSED
     BEFORE the cut is unchanged. A trigger that reads the future moves
     an earlier trade; a causal one cannot.

Usage:
  python plan/vs2_test.py --old C:/path/day-trading.PRE-VS2.py
"""
import importlib.util
import sys
from datetime import time as dtime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "plan"))
import rotation_sim as rs                      # noqa: E402  (loads dt)

dt = rs.dt
PTRAIL_KW = rs.build_simkw("PTRAIL6", rs.CFGS["PTRAIL6"], echo=False)
C37F_KW = rs.build_simkw("C37F", rs.CFGS["C37F"], echo=False)
for _kw in (PTRAIL_KW, C37F_KW):
    _kw["slippage_bps"] = 10.0
BUD = 15_000.0

# Days with real intraday structure (reused from fillmodel_test).
DAYS = [("TWG", "2025-09-11", 5.02), ("WFF", "2025-09-11", None),
        ("HSDT", "2025-06-11", None), ("BTCT", "2024-11-13", None),
        ("PCSA", "2025-06-17", None), ("NAMM", "2026-01-22", None),
        ("BNAI", "2026-06-05", None), ("SKYQ", "2026-04-02", None)]

# The VS2 kwarg sets under test. Each is the ENTRY trigger plus the
# minimum exit machinery needed for it to close a position; the full
# configs live in rotation_sim.CFGS (VS2 block).
BASE = dict(verbose=False, max_trades=1, buy_set=set(), orb=False,
            sell_mode="target_stop_only", trail_pct=999, stop_pct=8,
            pressure_trail=None, scale_out_at=None, wick_guard=3.0,
            max_vol_frac=0.20, vol_frac_window=10, vol_frac_causal=True,
            halt_aware=True, pm_spread_bps=50.0, slippage_bps=10.0,
            pullback_relax=True, struct_stop_bars=1)
VS2_KW = {
    "ORC": dict(BASE, or_clock=(dtime(9, 30), 5),
                struct_floor_mode="or_low", target_pct=10.0),
    "ORC-RT": dict(BASE, or_clock=(dtime(9, 30), 5),
                   orb_retest=(0.15, 20), target_r=2.0),
    "MICRO": dict(BASE, micro_pullback=(3, 3.0),
                  struct_floor_mode="sig_low", target_r=2.0),
    "EMAPB": dict(BASE, ema_pullback=(9, 0.25),
                  struct_floor_mode="sig_low", target_r=2.0),
    "FLAG": dict(BASE, flag_break=(6, 2.0, 5.0),
                 struct_floor_mode="sig_low", target_r=2.0),
    "VWRC": dict(BASE, vwap_entry=("reclaim",),
                 struct_floor_mode="sig_low", target_r=2.0),
    "VWBAND": dict(BASE, vwap_entry=("band", 1.0),
                   struct_floor_mode="sig_low", vwap_target=True,
                   target_pct=999.0),
    "EMAX": dict(BASE, or_clock=(dtime(9, 30), 5), ema_exit=9,
                 target_pct=999.0),
    "RANDE": dict(BASE, rand_entry=(60, "vs2-smoke"), target_r=2.0),
    "VWBNC": dict(BASE, vwap_entry=("bounce", 0.1),
                  struct_floor_mode="sig_low", target_r=2.0),
    "ABCD": dict(BASE, abcd_entry=(3.0, 0.62, 20),
                 struct_floor_mode="sig_low", target_r=2.0),
    "HALT": dict(BASE, halt_resume=(10,), struct_floor_mode="sig_low",
                 target_r=2.0),
}


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _win(df, start=dtime(7, 0)):
    return df[(df.index.time >= start) & (df.index.time < rs.EXIT_END)]


def _key(t):
    return (str(t["entry_time"]), t["entry"], str(t["exit_time"]),
            t["exit"], t["reason"], t["pnl"], t.get("shares"),
            t.get("trig"))


def identity(old_path):
    old = _load(old_path, "old_dt")
    bad, n = [], 0
    for sym, date, pc in DAYS:
        df = rs.bars_for(sym, date)
        if df is None:
            print(f"  identity: no bars for {sym} {date}")
            continue
        w = _win(df)
        for name, kw in (("PTRAIL", PTRAIL_KW), ("C37F", C37F_KW)):
            for es in (dtime(7, 0), dtime(9, 35), dtime(10, 30)):
                a = [_key(t) for t in old.simulate_trades(
                    w, prev_close=pc, budget=BUD, entry_start=es, **kw)]
                b = [_key(t) for t in dt.simulate_trades(
                    w, prev_close=pc, budget=BUD, entry_start=es, **kw)]
                n += 1
                if a != b:
                    bad.append((sym, date, name, str(es), a, b))
    print(f"  IDENTITY: {n - len(bad)}/{n} kwarg-day-start cells "
          f"byte-identical to the pre-VS2 engine")
    for row in bad[:5]:
        print("   MISMATCH", row[:4])
        print("     old", row[4])
        print("     new", row[5])
    assert not bad, "VS2 edit is NOT identity-preserving"


def smoke():
    fired = {k: 0 for k in VS2_KW}
    for sym, date, pc in DAYS:
        df = rs.bars_for(sym, date)
        if df is None:
            continue
        w = _win(df)
        for name, kw in VS2_KW.items():
            tr = dt.simulate_trades(w, prev_close=pc, budget=BUD,
                                    entry_start=dtime(9, 35), **kw)
            for t in tr:
                fired[name] += 1
                print(f"  smoke {name:<7} {sym:<5} {date} "
                      f"{t['entry_time']:%H:%M}@{t['entry']:<8.2f}-> "
                      f"{t['exit_time']:%H:%M}@{t['exit']:<8.2f} "
                      f"{t['reason']:<24} {t['pnl']:+9,.0f} "
                      f"trig={t.get('trig')}")
    print("  SMOKE fills per trigger:", fired)
    dead = [k for k, v in fired.items() if v == 0]
    if dead:
        print(f"  NOTE: no fill on these days for {dead} "
              f"(not a failure by itself)")


def poison(kw, df, pc, step=5, start=dtime(9, 35)):
    w = _win(df).astype(float)
    clean = dt.simulate_trades(w, prev_close=pc, budget=BUD,
                               entry_start=start, **kw)
    if not clean:
        return 0, 0
    first = w.index.get_loc(clean[0]["entry_time"])
    breaches = tested = 0
    cols = ["Open", "High", "Low", "Close", "Volume"]
    ci = [w.columns.get_loc(c) for c in cols]
    for cut in range(first + 1, len(w), step):
        for val in (9e9, 1e-9):
            p = w.copy()
            p.iloc[cut:, ci] = val
            tr = dt.simulate_trades(p, prev_close=pc, budget=BUD,
                                    entry_start=start, **kw)
            lim = w.index[cut]
            a = [_key(t) for t in clean if t["exit_time"] < lim]
            b = [_key(t) for t in tr if t["exit_time"] < lim]
            tested += 1
            if a != b:
                breaches += 1
                if breaches <= 2:
                    print(f"    breach at cut {lim:%H:%M} val {val}")
                    print(f"      clean {a}")
                    print(f"      pois  {b}")
    return breaches, tested


def causality():
    tot = n = 0
    for sym, date, pc in DAYS:
        df = rs.bars_for(sym, date)
        if df is None:
            continue
        for name, kw in VS2_KW.items():
            b, t = poison(kw, df, pc)
            tot += b
            n += t
            if t:
                print(f"  poison {name:<7} {sym:<5} {date} "
                      f"{b}/{t} breaches")
    print(f"  CAUSALITY: {tot}/{n} breaches across the VS2 triggers")
    assert tot == 0, "CAUSALITY BREACH in a VS2 trigger"


if __name__ == "__main__":
    argv = sys.argv[1:]
    old_path = None
    if "--old" in argv:
        old_path = argv[argv.index("--old") + 1]
    only = [a for a in argv if not a.startswith("--")
            and a != old_path]
    steps = only or ["identity", "smoke", "causality"]
    if "identity" in steps:
        if old_path:
            print("[1] identity vs pre-VS2 engine")
            identity(old_path)
        else:
            print("[1] identity SKIPPED (no --old snapshot given)")
    if "smoke" in steps:
        print("[2] smoke: do the new triggers fire?")
        smoke()
    if "causality" in steps:
        print("[3] poison test")
        causality()
    print("VS2 TESTS PASSED")
