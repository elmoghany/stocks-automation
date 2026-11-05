"""What made 2024 different for AMD and the best time-only rule (buy day 12, sell 7 days before). A description, not a rule."""
from pathlib import Path

import pandas as pd
import yfinance as yf

RES = Path(__file__).parent / "results"
raw = yf.download(["AMD", "QQQ", "SMH", "NVDA"], start="2022-06-01", end="2026-11-06", auto_adjust=True, progress=False)["Close"]
raw.index = pd.DatetimeIndex(raw.index).tz_localize(None).normalize()
print("calendar year returns")
for year in (2023, 2024, 2025, 2026):
    part = raw.loc[str(year)]
    base = raw.loc[:f"{year - 1}-12-31"].iloc[-1]
    print(f"  {year}: " + ", ".join(f"{k} {part[k].iloc[-1] / base[k] - 1:+.1%}" for k in ("AMD", "QQQ", "SMH", "NVDA")))
year = raw.loc["2024"]
print(f"AMD 2024: start {raw.AMD.loc[:'2023-12-31'].iloc[-1]:.2f}, high {year.AMD.max():.2f} on {year.AMD.idxmax().date()}, end {year.AMD.iloc[-1]:.2f}, from high {year.AMD.iloc[-1] / year.AMD.max() - 1:+.1%}")
above = raw.AMD > raw.AMD.rolling(200).mean()
print("share of days above the 200-day average: " + ", ".join(f"{y} {above.loc[str(y)].mean():.0%}" for y in (2024, 2025, 2026)))

tr = pd.read_csv(RES / "amd_grid_2024_trades.csv")
sma = raw.AMD.rolling(200).mean()
print("\ntrade: gain | best during | days to the best | AMD vs 200-day at buy | AMD minus SMH over the prior 3 months | QQQ during | SMH during")
for x in tr.itertuples():
    a, b = pd.Timestamp(x.bought), pd.Timestamp(x.sold)
    held = raw.AMD.loc[a:b]
    prior = raw.AMD.asof(a) / raw.AMD.loc[:a].iloc[-64] - raw.SMH.asof(a) / raw.SMH.loc[:a].iloc[-64]
    print(f"  {x.bought}: {x.gain:+.1%} | {x.best_gain:+.1%} | {held.values.argmax()} | {raw.AMD.asof(a) / sma.asof(a) - 1:+.1%} | {prior:+.1%} | {raw.QQQ.asof(b) / raw.QQQ.asof(a) - 1:+.1%} | {raw.SMH.asof(b) / raw.SMH.asof(a) - 1:+.1%}")

all_trades = pd.read_csv(RES / "amd_grid_2024_all_trades.csv")
all_trades["bought"] = pd.to_datetime(all_trades.bought)
all_trades["era"] = (all_trades.bought >= "2025-05-01").map({True: "May 2025 on (6 trades)", False: "through Feb 2025 (5 trades)"})
growth = all_trades.assign(f=1 + all_trades.gain_pct / 100).groupby(["era", "buy_day", "sell_before"]).f.prod().reset_index()
print("\naverage growth per $1 by sell day, across buy days")
print(growth.pivot_table(index="sell_before", columns="era", values="f").sort_index(ascending=False).round(2).to_string())
print("\naverage growth per $1 by buy day, across sell days")
print(growth.pivot_table(index="buy_day", columns="era", values="f").round(2).to_string())
