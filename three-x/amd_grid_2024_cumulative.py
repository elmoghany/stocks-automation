"""Cumulative % return after each sale for the best 10 combinations from January 2024, added to AMD_GRID_2024.md."""
from pathlib import Path

import pandas as pd

RES = Path(__file__).parent / "results"
MD = Path(__file__).parent / "AMD_GRID_2024.md"
t = pd.read_csv(RES / "amd_grid_2024_all_trades.csv")
grid = pd.read_csv(RES / "amd_grid_2024.csv").sort_values("value", ascending=False).head(10)
eq = pd.read_csv(RES / "curves_amd" / "AMD__amdcycle__Q_jan24_grid_hold.csv", usecols=["timestamp", "equity"], parse_dates=["timestamp"], index_col="timestamp").equity
eq.index = pd.DatetimeIndex(eq.index).tz_localize(None).normalize()
eq = eq[~eq.index.duplicated()].loc["2024-01-30":]
labels = [pd.Timestamp(q).strftime("%b%y") for q in sorted(t.quarter.unique())]
lines = ["Buy Sell " + " ".join(f"{x:>7s}" for x in labels)]
for r in grid.itertuples():
    part = t[(t.buy_day == r.buy_day) & (t.sell_before == r.sell_before)].sort_values("sold")
    lines.append(f"{r.buy_day:3d} {r.sell_before:4d} " + " ".join(f"{a / 1000 - 100:+7.1f}" for a in part.account))
top = grid.iloc[0]
dates = t[(t.buy_day == top.buy_day) & (t.sell_before == top.sell_before)].sort_values("sold").sold
lines.append("Hold     " + " ".join(f"{eq.asof(pd.Timestamp(d)) / eq.iloc[0] * 100 - 100:+7.1f}" for d in dates))
print("\n".join(lines))
print("hold end", round(eq.iloc[-1] / eq.iloc[0] * 100 - 100, 1), "dates", [str(d) for d in dates])
text = MD.read_text(encoding="utf-8")
head = "## Cumulative % return of the best 10, after each sale"
if head not in text:
    block = f"\n{head}\n\nFrom $100,000. The Hold row is AMD held, measured on the sale dates of the first line.\n\n```\n" + "\n".join(lines) + "\n```\n"
    MD.write_text(text + block, encoding="utf-8")
