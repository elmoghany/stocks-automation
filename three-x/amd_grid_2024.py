"""The buy and sell day grid again, ignoring the November 2023 trade (user order 2026-11-05): $100k from the 2024-01-30 report.

Time only, 121 combinations, in Vibe-Trading through 2026-11-05. AMD held starts on the same date.
Usage: venvs/vt/Scripts/python amd_grid_2024.py <lumibot job path>. Writes results/amd_grid_2024.csv and results/amd_grid_2024_trades.csv.
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
import amd_time_grid as G
import sweep

WINDOW, BEGIN = "jan24", "2024-01-30"
Q.WINDOWS[WINDOW] = BEGIN


def main():
    os.environ["VIBE_TRADING_ALLOWED_RUN_ROOTS"] = str(sweep.RUNS)
    os.environ["VIBE_TRADING_DATA_CACHE"] = "0"
    with mp.Pool(4, initializer=sweep.init_worker) as pool:
        for name, status, err in pool.imap_unordered(sweep.run_one, [Q.job(WINDOW, n) for n in list(G.NAMES.values()) + ["grid_hold"]]):
            if status == "error":
                print("ERROR", name, str(err)[:400])
    raw = yf.download("AMD", start=A.BASE["start"], end=Q.END, auto_adjust=True, progress=False)
    frame = pd.DataFrame({"close": raw["Close"].squeeze(), "open": raw["Open"].squeeze()}).dropna()
    frame.index = pd.DatetimeIndex(frame.index).tz_localize(None).normalize()
    reports = pd.to_datetime(A.REPORTS).sort_values()
    quarters = [q.date() for q in reports[(reports >= BEGIN)][:-1]]
    hold, hold_dd, _ = G.value(WINDOW, "grid_hold")
    rows = []
    for (d, b), name in G.NAMES.items():
        v, dd, eq = G.value(WINDOW, name)
        tr = pd.DataFrame(Q.trades_of(name, frame, reports))
        tr = tr[pd.to_datetime(tr.bought) >= BEGIN]
        g = tr.groupby("quarter").gain.apply(lambda s: np.prod(1 + s) - 1).reindex(quarters).fillna(0.0)
        rows.append({"buy_day": d, "sell_before": b, "value": v, "dd": dd, "q20": int((g >= .2).sum()), "q_loss": int((g < 0).sum()), "q_worst": g.min(), "q_median": g.median(), "q_best": g.max()})
    t = pd.DataFrame(rows)
    t.to_csv(A.RES / "amd_grid_2024.csv", index=False)
    pd.set_option("display.width", 200, "display.max_columns", 30)
    print(f"AMD held from {BEGIN}: ${hold:,.0f} (worst {hold_dd:.0%}); close {frame.close.iloc[-1]:.2f} on {frame.index[-1].date()}; {len(quarters)} quarters")
    print(f"{len(t)} combinations; beat held {(t.value > hold).sum()}; range ${t.value.min():,.0f} to ${t.value.max():,.0f}; median ${t.value.median():,.0f}")
    print((t.pivot(index="buy_day", columns="sell_before", values="value")[list(G.BEFORE)] / 1000).round(0).astype(int).to_string())
    print(t.groupby("sell_before").value.mean().round(0).astype(int).sort_index(ascending=False).to_string())
    print(t.groupby("buy_day").value.mean().round(0).astype(int).to_string())
    print(t.sort_values("value", ascending=False).head(10).to_string(index=False, float_format=lambda v: f"{v:,.2f}"))
    best = t.sort_values("value", ascending=False).iloc[0]
    name = G.NAMES[(int(best.buy_day), int(best.sell_before))]
    _, _, eq = G.value(WINDOW, name)
    tr = pd.DataFrame(Q.trades_of(name, frame, reports))
    tr = tr[pd.to_datetime(tr.bought) >= BEGIN]
    rows, before = [], eq.iloc[0]
    for x in tr.itertuples():
        after = eq.asof(pd.Timestamp(x.sold))
        held = frame.close.loc[pd.Timestamp(x.bought):pd.Timestamp(x.sold)]
        rows.append({"bought": x.bought, "buy": x.buy, "sold": x.sold, "sell": x.sell, "gain": x.gain, "made": after - before, "account": after, "best_gain": held.max() / x.buy - 1})
        before = after
    review = pd.DataFrame(rows)
    review.to_csv(A.RES / "amd_grid_2024_trades.csv", index=False)
    print(review.to_string(index=False, float_format=lambda v: f"{v:,.3f}"))
    print(f"winners {(review.made > 0).sum()} {review[review.made > 0].made.sum():,.0f}; losers {(review.made < 0).sum()} {review[review.made < 0].made.sum():,.0f}; biggest {review.made.max():,.0f} = {review.made.max() / review.made.sum():.0%} of profit; without it {review.account.iloc[-1] / (1 + review.loc[review.made.idxmax(), 'gain']):,.0f}")
    with open(sys.argv[1], "w", encoding="utf-8") as f:
        json.dump([{"name": sweep.key(*Q.job(WINDOW, name)), "codes": ["AMD"], "cfg": Q.job(WINDOW, name)[1], "start": BEGIN, "end": "2026-11-05"}], f)


if __name__ == "__main__":
    main()
