"""How far apart are buy-and-hold results of well-known large growth/semiconductor stocks over the same two windows? HINDSIGHT and SURVIVORSHIP: the list is today's famous names, chosen by me, not point-in-time.
It only shows the size of the prize for picking the stock rather than timing AMD: it does not say a rule could have found the winner.
"""
import numpy as np
import pandas as pd
import yfinance as yf
from common import *

f = load_amd()
W = windows(f.index)
names = ["AMD", "NVDA", "AVGO", "MU", "TSM", "QCOM", "INTC", "TXN", "AAPL", "MSFT", "AMZN", "GOOGL", "META", "TSLA", "NFLX", "SMH", "QQQ"]
rows = []
for code in names:
    path = DATA / f"{code}_disp.csv"
    if code == "AMD":
        d = f
    else:
        if not path.exists():
            raw = yf.download(code, start="2012-06-01", end="2026-11-12", auto_adjust=True, progress=False)
            d = pd.DataFrame({k.lower(): raw[k].squeeze() for k in ("Open", "Close")}).dropna()
            d.index = pd.DatetimeIndex(d.index).tz_localize(None).normalize()
            d.to_csv(path)
        d = pd.read_csv(path, index_col=0, parse_dates=True)
    row = {"ticker": code}
    for w in ("recent", "early"):
        lo_d, hi_d = f.index[W[w][0]], f.index[W[w][1] - 1]
        x = d[(d.index >= lo_d) & (d.index <= hi_d)]
        if len(x) < 100 or x.index[0] > lo_d + pd.Timedelta(days=10):
            row[w] = np.nan
        else:
            row[w] = x.close.iloc[-1] / x.open.iloc[0]
    rows.append(row)
T = pd.DataFrame(rows)
amd = T.set_index("ticker").loc["AMD"]
T["recent_vs_AMD"] = T["recent"] / amd["recent"]
T["early_vs_AMD"] = T["early"] / amd["early"]
T.to_csv(OUT / "d8_dispersion.csv", index=False)
print(T.to_string(index=False, float_format=lambda v: f"{v:,.2f}"))
