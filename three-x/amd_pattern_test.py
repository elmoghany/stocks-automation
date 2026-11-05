"""Backtest the pattern from amd_pattern.py in Vibe-Trading, $100k, cash between trades, next-open fills, 5 bp slippage.

The pattern was read from these same reports, so this shows what it would have made, not evidence that it will work again.
Usage: venvs/vt/Scripts/python amd_pattern_test.py <lumibot job path>
"""
import importlib.util
import json
import multiprocessing as mp
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

import amd_cycle as A
import sweep

END = "2026-11-06"
WINDOWS = {"oct25": "2025-10-01", "3y": A.FROM}
RULES = {"hold": {"rule": "hold", "cadence": "W"},
         "dip10_else_day13": {"rule": "pattern", "cadence": "D", "entry": 13, "exit": 48, "dip": 0.10, "dip_days": 13, "then": "buy"},
         "day13": {"rule": "pattern", "cadence": "D", "entry": 13, "exit": 48, "dip": 0, "then": "buy"},
         "dip10_or_skip": {"rule": "pattern", "cadence": "D", "entry": 13, "exit": 48, "dip": 0.10, "dip_days": 20, "then": "skip"}}

spec = importlib.util.spec_from_file_location("signal_template", Path(__file__).parent / "signal_template.py")
rules = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rules)


def job(window, name):
    return ["AMD"], {**A.BASE, "end": END, "trade_from": WINDOWS[window], **RULES[name], "tag": f"P_{window}_{name}"}


def main():
    os.environ["VIBE_TRADING_ALLOWED_RUN_ROOTS"] = str(sweep.RUNS)
    os.environ["VIBE_TRADING_DATA_CACHE"] = "0"  # today's bar is needed
    jobs = [job(w, n) for w in WINDOWS for n in RULES]
    with mp.Pool(4, initializer=sweep.init_worker) as pool:
        for name, status, err in pool.imap_unordered(sweep.run_one, jobs):
            if status == "error":
                print("ERROR", name, str(err)[:400])
    raw = yf.download("AMD", start=A.BASE["start"], end=END, auto_adjust=True, progress=False)
    frame = pd.DataFrame({"close": raw["Close"].squeeze(), "open": raw["Open"].squeeze()}).dropna()
    frame.index = pd.DatetimeIndex(frame.index).tz_localize(None).normalize()
    rows = []
    for window, begin in WINDOWS.items():
        for name in RULES:
            eq = pd.read_csv(A.RES / "curves_amd" / f"AMD__amdcycle__P_{window}_{name}.csv", usecols=["timestamp", "equity"], parse_dates=["timestamp"], index_col="timestamp").equity
            eq.index = pd.DatetimeIndex(eq.index).tz_localize(None).normalize()
            eq = eq[~eq.index.duplicated()].loc[begin:]
            sig = rules._amdcycle(frame, job(window, name)[1]).reindex(eq.index).fillna(0.0)
            rows.append({"window": window, "rule": name, "end_value": eq.iloc[-1], "multiple": eq.iloc[-1] / eq.iloc[0], "max_dd": float(np.min(eq / eq.cummax() - 1)),
                         "in_market": float(sig.mean()), "round_trips": int((sig.diff().fillna(0) > 0).sum() + (sig.iloc[0] > 0)), "last_day": str(eq.index[-1].date())})
            if name != "hold":
                print(f"\n{window} {name}, trades (signal at the close, filled next open)")
                pos = rules._amdcycle(frame, job(window, name)[1])
                pos = pos[pos.index >= begin]
                changes = pos[pos.diff().fillna(pos) != 0]
                buy = None
                for day, val in changes.items():
                    following = frame.index[frame.index > day]
                    fill = frame.open.loc[following[0]] if len(following) else float("nan")
                    if val:
                        buy = fill
                        print(f"  buy  signal {day.date()} close {frame.close.loc[day]:.2f}, fill {fill:.2f}")
                    else:
                        print(f"  sell signal {day.date()} close {frame.close.loc[day]:.2f}, fill {fill:.2f}, trade {fill / buy - 1:+.1%}")
                print(f"  now {'holding' if pos.iloc[-1] else 'in cash'}" + (" (signal today, fills at the next open)" if pos.iloc[-1] and pos.index[-1] == pos[pos.diff() > 0].index[-1] else ""))
    table = pd.DataFrame(rows)
    table.to_csv(A.RES / "amd_pattern_test.csv", index=False)
    pd.set_option("display.width", 200, "display.max_columns", 20)
    print()
    print(table.to_string(index=False, float_format=lambda v: f"{v:,.2f}"))
    lb = [{"name": sweep.key(*job("oct25", n)), "codes": ["AMD"], "cfg": job("oct25", n)[1], "start": "2025-10-01", "end": "2026-11-05"} for n in ("dip10_else_day13", "hold")]
    with open(sys.argv[1], "w", encoding="utf-8") as f:
        json.dump(lb, f)


if __name__ == "__main__":
    main()
