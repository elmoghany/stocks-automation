"""A wide search of buy and sell days, AMD, $100k from the 2024-01-30 report. Time only, in Vibe-Trading through 2026-11-05.

Buy day 1-45 after a report, sell 1-40 trading days before the next report, leaving out pairs that add up to more than 55, which would
hold for under about a week and a half. Each pair is also scored on two periods, because the best dates flipped between them:
trades through the Feb 2025 report (weak for AMD) and from the May 2025 report on (strong).
Writes results/amd_wide_grid.csv. Usage: venvs/vt/Scripts/python amd_wide_grid.py
"""
import multiprocessing as mp
import os

import numpy as np
import pandas as pd
import yfinance as yf

import amd_cycle as A
import amd_grid_2024 as B
import amd_quarters as Q
import amd_time_grid as G
import sweep

PAIRS = [(d, b) for d in range(1, 46) for b in range(1, 41) if d + b <= 55]
NAMES = {p: f"time_d{p[0]}_before{p[1]}" for p in PAIRS}
for (d, b), name in NAMES.items():
    Q.RULES[name] = {"rule": "quarter", "cadence": "D", "buy_on": "day", "day": d, "before_next": b}


def main():
    os.environ["VIBE_TRADING_ALLOWED_RUN_ROOTS"] = str(sweep.RUNS)
    os.environ["VIBE_TRADING_DATA_CACHE"] = "1"
    os.environ["VIBE_TRADING_DATA_CACHE_ROOT"] = r"E:\strategy-repos\vt_cache"
    done, total = 0, len(NAMES)
    with mp.Pool(4, initializer=sweep.init_worker) as pool:
        for name, status, err in pool.imap_unordered(sweep.run_one, [Q.job(B.WINDOW, n) for n in NAMES.values()]):
            done += 1
            if status == "error":
                print("ERROR", name, str(err)[:300], flush=True)
            if done % 100 == 0:
                print(f"{done}/{total}", flush=True)
    raw = yf.download("AMD", start=A.BASE["start"], end=Q.END, auto_adjust=True, progress=False)
    frame = pd.DataFrame({"close": raw["Close"].squeeze(), "open": raw["Open"].squeeze()}).dropna()
    frame.index = pd.DatetimeIndex(frame.index).tz_localize(None).normalize()
    reports = pd.to_datetime(A.REPORTS).sort_values()
    quarters = [q.date() for q in reports[reports >= B.BEGIN][:-1]]
    hold, hold_dd, heq = G.value(B.WINDOW, "grid_hold")
    rows = []
    for (d, b), name in NAMES.items():
        v, dd, eq = G.value(B.WINDOW, name)
        tr = pd.DataFrame(Q.trades_of(name, frame, reports))
        tr = tr[pd.to_datetime(tr.bought) >= B.BEGIN]
        g = tr.groupby("quarter").gain.apply(lambda s: np.prod(1 + s) - 1).reindex(quarters).fillna(0.0)
        rows.append({"buy_day": d, "sell_before": b, "value": v, "dd": dd, "weak": np.prod(1 + g.iloc[:5]), "strong": np.prod(1 + g.iloc[5:]), "q20": int((g >= .2).sum()), "q_loss": int((g < 0).sum()), "q_worst": g.min(), "q_median": g.median()})
    t = pd.DataFrame(rows)
    t["both"] = t[["weak", "strong"]].min(axis=1)
    around = []
    for r in t.itertuples():
        cells = t[(abs(t.buy_day - r.buy_day) <= 2) & (abs(t.sell_before - r.sell_before) <= 2)]
        around.append(cells.value.mean())
    t["area"] = around
    t.to_csv(A.RES / "amd_wide_grid.csv", index=False)
    pd.set_option("display.width", 220, "display.max_columns", 30, "display.max_rows", 60)
    fmt = lambda v: f"{v:,.2f}"
    close = frame.close
    print(f"AMD held ${hold:,.0f}, worst {hold_dd:.0%}; through Nov 4 ${heq.loc[:'2026-11-04'].iloc[-1]:,.0f}. Weak period held {close.asof(pd.Timestamp('2025-05-06')) / close.asof(pd.Timestamp(B.BEGIN)):.2f}x; strong period held {close.iloc[-1] / close.asof(pd.Timestamp('2025-05-06')):.2f}x")
    print(f"{len(t)} pairs; beat held {(t.value > hold).sum()}; range ${t.value.min():,.0f} to ${t.value.max():,.0f}; median ${t.value.median():,.0f}; made money in the weak period {(t.weak > 1).sum()}")
    print("\ntop 10 by final value")
    print(t.sort_values("value", ascending=False).head(10).to_string(index=False, float_format=fmt))
    print("\ntop 10 by the area around them")
    print(t.sort_values("area", ascending=False).head(10).to_string(index=False, float_format=fmt))
    print("\ntop 10 by the weaker of the two periods")
    print(t.sort_values("both", ascending=False).head(10).to_string(index=False, float_format=fmt))
    print("\ntop 10 in the weak period")
    print(t.sort_values("weak", ascending=False).head(10).to_string(index=False, float_format=fmt))
    print("\ntop 10 in the strong period")
    print(t.sort_values("strong", ascending=False).head(10).to_string(index=False, float_format=fmt))
    bins_d = pd.cut(t.buy_day, [0, 5, 10, 15, 20, 25, 30, 35, 40, 45])
    bins_b = pd.cut(t.sell_before, [0, 5, 10, 15, 20, 25, 30, 35, 40])
    for label, col, f in (("final value in $k", "value", 1000), ("weak period, $1 becomes", "weak", 1), ("strong period, $1 becomes", "strong", 1), ("worst fall", "dd", 1)):
        print(f"\naverage {label}: buy days (rows), days before the next report to sell (columns)")
        view = t.groupby([bins_d, bins_b], observed=True)[col].mean().unstack() / f
        print(view.round(2 if f == 1 else 0).to_string())


if __name__ == "__main__":
    main()
