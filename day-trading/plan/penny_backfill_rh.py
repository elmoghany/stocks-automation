"""Backfill sim: run both strategy configs on the Robinhood 5-min CSVs for
the days missing from the yfinance 60-day backtest. Combines with the prior
results (A +$293.33, B +$833.22 over 28 days)."""

import importlib.util
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent))
_spec = importlib.util.spec_from_file_location("pennystocks",
                                               ROOT / "day-trading.py")
ps = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ps)

# (symbol, date) -> prev_close from the discovery cache
gappers = json.loads((ROOT / "data/backtest60/gapper_days.json").read_text())
prev_map = {(g["symbol"], g["date"]): g["prev_close"] for g in gappers}

DAYS = [("PIII", "2026-05-15"), ("AMST", "2026-05-19"),
        ("BIYA", "2026-05-22"), ("CPSH", "2026-05-26"),
        ("QTTB", "2026-05-27"), ("TGHL", "2026-06-01")]

PRIOR = {"A": 293.33, "B": 833.22}

tot = {"A": 0.0, "B": 0.0}
print(f"{'date':<12} {'sym':<6} {'prev':>7} | {'A trades':>8} {'A P&L':>9} "
      f"| {'B trades':>8} {'B P&L':>9}")
print("-" * 70)
for sym, date in DAYS:
    f = ROOT / f"data/rh_bars/{sym}_{date}.csv"
    df = pd.read_csv(f)
    df["begins_at"] = (pd.to_datetime(df["begins_at"], utc=True)
                       .dt.tz_convert(ps.ET))
    df = df.rename(columns={"open": "Open", "high": "High", "low": "Low",
                            "close": "Close", "volume": "Volume"})
    df = df.set_index("begins_at").sort_index()
    prev = prev_map.get((sym, date))
    a = ps.simulate_trades(df, verbose=False, prev_close=prev)
    b = ps.simulate_trades(df, verbose=False, buy_set=None, vol_confirm=False,
                           trail_pct=20, stop_pct=5, prev_close=prev)
    pa = sum(t["pnl"] for t in a)
    pb = sum(t["pnl"] for t in b)
    tot["A"] += pa
    tot["B"] += pb
    print(f"{date:<12} {sym:<6} {prev:>7.2f} | {len(a):>8} {pa:>+9.2f} "
          f"| {len(b):>8} {pb:>+9.2f}")

print("-" * 70)
print(f"Backfill totals:      A {tot['A']:+.2f}   B {tot['B']:+.2f}")
print(f"Prior 28-day totals:  A {PRIOR['A']:+.2f}   B {PRIOR['B']:+.2f}")
print(f"COMBINED 60-day:      A {PRIOR['A'] + tot['A']:+.2f} "
      f"({(PRIOR['A'] + tot['A']) / 10:+.1f}% on $1000)   "
      f"B {PRIOR['B'] + tot['B']:+.2f} "
      f"({(PRIOR['B'] + tot['B']) / 10:+.1f}% on $1000)")
