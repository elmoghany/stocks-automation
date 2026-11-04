"""How often does a stock in that January's top-50 halal list triple within the next 12 months?"""
import json
from pathlib import Path

import pandas as pd

HERE = Path(__file__).parent
pit = json.loads((HERE / "results" / "pit_top50.json").read_text(encoding="utf-8"))
rows = []
for f in (HERE / "results" / "curves").glob("*__bh.csv"):
    ticker = f.name.split("__")[0]
    if "+" in ticker:
        continue
    s = pd.read_csv(f, parse_dates=["timestamp"], index_col="timestamp")["equity"]
    s.index = pd.DatetimeIndex(s.index).tz_localize(None)
    forward = (s.shift(-252) / s).dropna()
    for day, multiple in forward.items():
        year = str(day.year)
        if year in pit and ticker in pit[year]["halal"]:
            rows.append((day, ticker, multiple))
df = pd.DataFrame(rows, columns=["day", "ticker", "multiple"])
print("covered tickers", df.ticker.nunique(), "of the bh curves; stock-windows", len(df))
print(f"share >=3x {(df.multiple >= 3).mean():.2%}, >=2x {(df.multiple >= 2).mean():.2%}, median {df.multiple.median():.2f}x")
print("3x windows by ticker:", df[df.multiple >= 3].groupby("ticker").size().sort_values(ascending=False).to_dict())
print("3x share by start year:", (df.groupby(df.day.dt.year).multiple.apply(lambda m: (m >= 3).mean()) * 100).round(1).to_dict())
