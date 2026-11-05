"""Every sale of all 121 buy and sell day combinations, $100k from the 2024-01-30 report. Reads the runs from amd_grid_2024.py.

Writes results/amd_grid_2024_all_trades.csv (one row per sale) and AMD_GRID_2024.md (one line per combination, readable).
"""
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

import amd_cycle as A
import amd_grid_2024 as B
import amd_quarters as Q
import amd_time_grid as G

raw = yf.download("AMD", start=A.BASE["start"], end=Q.END, auto_adjust=True, progress=False)
frame = pd.DataFrame({"close": raw["Close"].squeeze(), "open": raw["Open"].squeeze()}).dropna()
frame.index = pd.DatetimeIndex(frame.index).tz_localize(None).normalize()
reports = pd.to_datetime(A.REPORTS).sort_values()
quarters = [q.date() for q in reports[reports >= B.BEGIN][:-1]]
labels = [pd.Timestamp(q).strftime("%b%y") for q in quarters]
hold, hold_dd, heq = G.value(B.WINDOW, "grid_hold")
hold_nov4 = heq.loc[:"2026-11-04"].iloc[-1]
rows, lines = [], []
for (d, b), name in G.NAMES.items():
    v, dd, eq = G.value(B.WINDOW, name)
    tr = pd.DataFrame(Q.trades_of(name, frame, reports))
    tr = tr[pd.to_datetime(tr.bought) >= B.BEGIN]
    before, per = eq.iloc[0], {}
    for x in tr.itertuples():
        after = eq.asof(pd.Timestamp(x.sold))
        rows.append({"buy_day": d, "sell_before": b, "quarter": x.quarter, "bought": x.bought, "buy": round(x.buy, 2), "sold": x.sold, "sell": round(x.sell, 2), "gain_pct": round(x.gain * 100, 1), "made": round(after - before, 2), "account": round(after, 2)})
        per[x.quarter] = x.gain
        before = after
    lines.append((v, d, b, dd, [per.get(q) for q in quarters]))
all_trades = pd.DataFrame(rows)
all_trades.to_csv(A.RES / "amd_grid_2024_all_trades.csv", index=False)
lines.sort(key=lambda r: -r[0])
text = ["# AMD buy and sell day grid, $100,000 from the January 30, 2024 report", "",
        f"Backtest in Vibe-Trading through 2026-11-05, time only. AMD held from the same date: ${hold:,.0f} (worst fall {hold_dd:.0%}), or ${hold_nov4:,.0f} through the November 4 close, before the November 5 fall. Every combination was in cash on November 5.", "",
        "Each line is one combination, best first: buy day after a report, trading days before the next report to sell, final value, worst fall, then the % gain of each quarter's trade.", "", "```",
        "Buy Sell    Final    Fall  " + " ".join(f"{x:>6s}" for x in labels)]
for v, d, b, dd, gains in lines:
    text.append(f"{d:3d} {b:4d} {v:9,.0f}  {dd:5.0%}  " + " ".join(f"{g * 100:+6.1f}" if g is not None else f"{'':>6s}" for g in gains))
text += ["```", "", "Every sale with dates, prices and dollars is in `results/amd_grid_2024_all_trades.csv`."]
(Path(__file__).parent / "AMD_GRID_2024.md").write_text("\n".join(text) + "\n", encoding="utf-8")
values = np.array([r[0] for r in lines])
print(f"held {hold:,.0f}; held through Nov 4 {hold_nov4:,.0f}; beat held {(values > hold).sum()}; beat held through Nov 4 {(values > hold_nov4).sum()} of {len(values)}")
print(f"final value: min {values.min():,.0f}, quartiles {np.percentile(values, 25):,.0f} / {np.median(values):,.0f} / {np.percentile(values, 75):,.0f}, max {values.max():,.0f}; rows {len(all_trades)}")
print("\nby quarter across all 121: worst, median, best trade %, share winning, and AMD report to report")
for q, lab in zip(quarters, labels):
    g = all_trades[all_trades.quarter == q].gain_pct
    nxt = reports[reports > pd.Timestamp(q)][0]
    amd = frame.close.asof(nxt) / frame.close.asof(pd.Timestamp(q)) - 1
    print(f"{lab}: {g.min():+6.1f} {g.median():+6.1f} {g.max():+6.1f}  won {int((g > 0).sum()):3d} of {len(g)}  AMD {amd * 100:+6.1f}")
full = all_trades.pivot(index=["buy_day", "sell_before"], columns="quarter", values="gain_pct")
print("\nquarters at +20%: range", int((full >= 20).sum(axis=1).min()), "to", int((full >= 20).sum(axis=1).max()), "; losing quarters: range", int((full < 0).sum(axis=1).min()), "to", int((full < 0).sum(axis=1).max()))
print("final value in %, buy day by sell day")
t = pd.read_csv(A.RES / "amd_grid_2024.csv")
print(((t.pivot(index="buy_day", columns="sell_before", values="value")[list(G.BEFORE)] / 1000 - 100)).round(0).astype(int).to_string())
print((t.pivot(index="buy_day", columns="sell_before", values="dd")[list(G.BEFORE)] * 100).round(0).astype(int).to_string())
