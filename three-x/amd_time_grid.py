"""Every combination of buy day (10-20 after a report) and sell day (5-15 before the next report), AMD, last 3 years.

Time only, no price triggers. Runs in Vibe-Trading, $100k, cash between trades, next-open fills, 5 bp slippage, data through
2026-11-05. "Neighbors" averages the cells next to a combination: a real timing effect should not depend on one exact day.
Ranking on the first 8 quarters and scoring on the last 4 shows how well the choice would have held up.

Usage: venvs/vt/Scripts/python amd_time_grid.py <lumibot job path>. Writes results/amd_time_grid.csv.
"""
import json
import multiprocessing as mp
import os
import sys

import numpy as np
import pandas as pd
import yfinance as yf

import amd_cycle as A
import amd_quarters as Q
import sweep

DAYS, BEFORE = range(10, 21), range(15, 4, -1)
NAMES = {(d, b): f"time_d{d}_before{b}" for d in DAYS for b in BEFORE}
Q.RULES["grid_hold"] = {"rule": "hold", "cadence": "W"}
for (d, b), name in NAMES.items():
    Q.RULES[name] = {"rule": "quarter", "cadence": "D", "buy_on": "day", "day": d, "before_next": b}


def value(window, name):
    eq = pd.read_csv(A.RES / "curves_amd" / f"AMD__amdcycle__Q_{window}_{name}.csv", usecols=["timestamp", "equity"], parse_dates=["timestamp"], index_col="timestamp").equity
    eq.index = pd.DatetimeIndex(eq.index).tz_localize(None).normalize()
    eq = eq[~eq.index.duplicated()].loc[Q.WINDOWS[window]:]
    return eq.iloc[-1], float(np.min(eq / eq.cummax() - 1)), eq


def main():
    os.environ["VIBE_TRADING_ALLOWED_RUN_ROOTS"] = str(sweep.RUNS)
    os.environ["VIBE_TRADING_DATA_CACHE"] = "0"
    jobs = [Q.job(w, n) for w in Q.WINDOWS for n in list(NAMES.values()) + ["grid_hold"]]
    with mp.Pool(4, initializer=sweep.init_worker) as pool:
        for name, status, err in pool.imap_unordered(sweep.run_one, jobs):
            if status == "error":
                print("ERROR", name, str(err)[:400])
    raw = yf.download("AMD", start=A.BASE["start"], end=Q.END, auto_adjust=True, progress=False)
    frame = pd.DataFrame({"close": raw["Close"].squeeze(), "open": raw["Open"].squeeze()}).dropna()
    frame.index = pd.DatetimeIndex(frame.index).tz_localize(None).normalize()
    reports = pd.to_datetime(A.REPORTS).sort_values()
    done = reports[reports >= "2023-10-01"]
    quarters = [q.date() for q in done[:-1]]
    rows, gains = [], {}
    for (d, b), name in NAMES.items():
        v3, dd3, eq = value("3y", name)
        vo, ddo, _ = value("oct25", name)
        tr = pd.DataFrame(Q.trades_of(name, frame, reports))
        g = tr.groupby("quarter").gain.apply(lambda s: np.prod(1 + s) - 1).reindex(quarters).fillna(0.0)
        gains[(d, b)] = g
        x = eq.values
        win = np.array([x[i + 252] / x[i] for i in range(0, len(x) - 252, 21)])
        rows.append({"buy_day": d, "sell_before": b, "value_3y": v3, "dd_3y": dd3, "value_oct25": vo, "dd_oct25": ddo, "q20": int((g >= .2).sum()), "q_loss": int((g < 0).sum()), "q_worst": g.min(), "q_median": g.median(),
                     "first8": np.prod(1 + g.iloc[:8]), "last4": np.prod(1 + g.iloc[8:]), "last4_q20": int((g.iloc[8:] >= .2).sum()), "windows_2x": float((win >= 2).mean()), "windows_3x": float((win >= 3).mean())})
    t = pd.DataFrame(rows)
    grid3 = t.pivot(index="buy_day", columns="sell_before", values="value_3y")[list(BEFORE)]
    around = []
    for r in t.itertuples():
        cells = t[(abs(t.buy_day - r.buy_day) <= 1) & (abs(t.sell_before - r.sell_before) <= 1) & ~((t.buy_day == r.buy_day) & (t.sell_before == r.sell_before))]
        around.append(cells.value_3y.mean())
    t["neighbors_3y"] = around
    t.to_csv(A.RES / "amd_time_grid.csv", index=False)
    pd.set_option("display.width", 200, "display.max_columns", 30)
    hold3, hold3_dd, heq = value("3y", "grid_hold")
    holdo, holdo_dd, _ = value("oct25", "grid_hold")
    print(f"AMD held: 3 years ${hold3:,.0f} (worst {hold3_dd:.0%}); since Oct 2025 ${holdo:,.0f} (worst {holdo_dd:.0%}); last close {frame.close.iloc[-1]:.2f} on {frame.index[-1].date()}")
    print(f"{len(t)} combinations. Beat held: 3 years {(t.value_3y > hold3).sum()}, since Oct 2025 {(t.value_oct25 > holdo).sum()}")
    print("\n3-year value in $k: buy day (rows), days before the next report to sell (columns)")
    print((grid3 / 1000).round(0).astype(int).to_string())
    print("\nvalue since Oct 2025 in $k")
    print((t.pivot(index="buy_day", columns="sell_before", values="value_oct25")[list(BEFORE)] / 1000).round(0).astype(int).to_string())
    print("\nquarters at 20%+ (of 12)")
    print(t.pivot(index="buy_day", columns="sell_before", values="q20")[list(BEFORE)].to_string())
    print("\naverage 3-year value by buy day")
    print(t.groupby("buy_day").value_3y.mean().round(0).astype(int).to_string())
    print("\naverage 3-year value by sell day")
    print(t.groupby("sell_before").value_3y.mean().round(0).astype(int).sort_index(ascending=False).to_string())
    show = ["buy_day", "sell_before", "value_3y", "neighbors_3y", "dd_3y", "value_oct25", "dd_oct25", "q20", "q_loss", "q_worst", "q_median", "last4", "windows_2x", "windows_3x"]
    fmt = lambda v: f"{v:,.2f}"
    print("\ntop 6 by 3-year value")
    print(t.sort_values("value_3y", ascending=False).head(6)[show].to_string(index=False, float_format=fmt))
    print("\ntop 6 by value since Oct 2025")
    print(t.sort_values("value_oct25", ascending=False).head(6)[show].to_string(index=False, float_format=fmt))
    print("\ntop 6 by quarters at 20%+")
    print(t.sort_values(["q20", "value_3y"], ascending=False).head(6)[show].to_string(index=False, float_format=fmt))
    print("\ntop 6 by neighbors")
    print(t.sort_values("neighbors_3y", ascending=False).head(6)[show].to_string(index=False, float_format=fmt))
    px = pd.Series(frame.close.values, index=frame.index)
    pick = t.sort_values("first8", ascending=False).iloc[0]
    top = t.sort_values("first8", ascending=False).head(10)
    print(f"\nranked on the first 8 quarters: buy {pick.buy_day:.0f}, sell {pick.sell_before:.0f} before: {pick.first8:.2f}x, then {pick.last4:.2f}x in the last 4 ({pick.last4_q20:.0f} of 4 at 20%+). Top 10 median in the last 4: {top.last4.median():.2f}x. All 66: {t.last4.min():.2f}x to {t.last4.max():.2f}x. AMD held last 4: {px.asof(done[-1]) / px.asof(done[8]):.2f}x")
    best = t.sort_values("value_3y", ascending=False).iloc[0]
    name = NAMES[(int(best.buy_day), int(best.sell_before))]
    print(f"\ntrades of the best: buy day {best.buy_day:.0f}, sell {best.sell_before:.0f} days before")
    tr = pd.DataFrame(Q.trades_of(name, frame, reports))
    print(tr.drop(columns="rule").to_string(index=False, float_format=lambda v: f"{v:.2f}"))
    jobs = [{"name": sweep.key(*Q.job(w, name)), "codes": ["AMD"], "cfg": Q.job(w, name)[1], "start": Q.WINDOWS[w], "end": "2026-11-05"} for w in Q.WINDOWS]
    with open(sys.argv[1], "w", encoding="utf-8") as f:
        json.dump(jobs, f)


if __name__ == "__main__":
    main()
